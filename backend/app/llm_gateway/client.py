"""
LLM Gateway — central async completion client.

All agent LLM calls go through LLMClient.complete().
Handles:
  - Model selection via task_type routing (router.py)
  - Async LiteLLM call with configurable timeout
  - Automatic fallback when primary model is unavailable
  - Usage recording to llm_usage table (tracker.py)
  - OpenTelemetry span per call (gracefully no-ops when OTel exporter unavailable)
  - structlog entries (never logging prompt content or API keys)

Usage
-----
    from app.llm_gateway.client import LLMClient

    client = LLMClient()
    response = await client.complete(
        task_type="structured_extraction",
        messages=[{"role": "user", "content": "..."}],
        db=db_session,                    # AsyncSession — required for tracking
        agent_exec_id="uuid...",          # optional
        event_id="uuid...",               # optional
    )
    text = response.choices[0].message.content
"""

from __future__ import annotations

import asyncio
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import litellm  # module-level so tests can patch app.llm_gateway.client.litellm
import structlog

from app.llm_gateway.router import get_route, extract_provider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

log = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Lazy OTel tracer — avoids hard dependency on opentelemetry-exporter-otlp-proto-grpc
# at import time.  Falls back to the no-op tracer when the exporter package is
# not installed in the current environment (e.g. local unit-test runs).
# ---------------------------------------------------------------------------

def _get_tracer():
    """Return an OTel tracer, falling back to the no-op tracer on ImportError."""
    try:
        from app.observability.tracing import get_tracer  # noqa: PLC0415
        return get_tracer("llm_gateway")
    except (ImportError, Exception):
        from opentelemetry import trace  # noqa: PLC0415
        return trace.get_tracer("llm_gateway")


@contextmanager
def _safe_span(task_type: str):
    """
    Context manager that wraps a single OTel span.

    Silently falls back to a no-op span when the OTel exporter is unavailable.
    Exceptions raised inside the ``with`` block propagate normally — they are
    never suppressed here.
    """
    try:
        tracer = _get_tracer()
        with tracer.start_as_current_span(f"llm.{task_type}") as span:
            yield span
        # If we reach here the body completed without raising — nothing more to do.
    except LLMGatewayError:
        raise  # always propagate our own gateway errors unchanged
    except Exception:
        # OTel setup failed (exporter not installed, Jaeger unreachable, etc.)
        # Use a no-op span and yield to the caller — their exceptions will propagate.
        span = _NoOpSpan()
        yield span


class _NoOpSpan:
    """Minimal stand-in for an OTel span when the real tracer is unavailable."""

    def set_attribute(self, key: str, value: Any) -> None:  # noqa: D102
        pass


# ---------------------------------------------------------------------------
# Public types
# ---------------------------------------------------------------------------


class LLMGatewayError(Exception):
    """Raised when all providers (primary + fallbacks) have been exhausted."""

    def __init__(self, task_type: str, attempted: list[str], last_error: Exception) -> None:
        self.task_type = task_type
        self.attempted = attempted
        self.last_error = last_error
        super().__init__(
            f"All LLM providers failed for task_type='{task_type}'. "
            f"Attempted: {attempted}. Last error: {last_error}"
        )


@dataclass
class CompletionResult:
    """Wrapper around a LiteLLM ModelResponse with gateway metadata."""

    response: Any                      # litellm.ModelResponse
    model_used: str                    # actual model that succeeded
    provider: str                      # short provider name
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int
    fallback_used: bool = False
    fallback_reason: str | None = None

    @property
    def content(self) -> str:
        """Convenience accessor for the first choice message content."""
        try:
            return self.response.choices[0].message.content or ""
        except (AttributeError, IndexError):
            return ""


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LLMClient:
    """
    Centralized LLM client for all agent calls.

    Thread-safe: each call is independent.
    Instantiate once and reuse across the app lifetime.
    """

    def __init__(
        self,
        default_timeout: float = 60.0,
        max_retries_per_model: int = 1,
    ) -> None:
        self._timeout = default_timeout
        self._max_retries = max_retries_per_model

    async def complete(
        self,
        task_type: str,
        messages: list[dict[str, str]],
        db: AsyncSession,
        *,
        agent_exec_id: str | None = None,
        event_id: str | None = None,
        max_tokens: int = 2048,
        temperature: float = 0.1,
        **litellm_kwargs: Any,
    ) -> CompletionResult:
        """
        Execute an LLM completion request with automatic fallback.

        Parameters
        ----------
        task_type       One of the keys in TASK_ROUTING (e.g. "structured_extraction").
        messages        OpenAI-format message list.
        db              Active AsyncSession for writing usage records.
        agent_exec_id   Optional FK to agent_executions row.
        event_id        Optional FK to events row.
        max_tokens      Maximum completion tokens.
        temperature     Sampling temperature.
        **litellm_kwargs  Additional kwargs forwarded to litellm.acompletion().

        Returns
        -------
        CompletionResult with response + gateway metadata.

        Raises
        ------
        LLMGatewayError  When all providers fail.
        ValueError        When task_type is unknown.
        """
        # Deferred import — avoids pulling geoalchemy2 at module level
        from app.llm_gateway.tracker import record_usage, extract_usage_from_response  # noqa: PLC0415

        route = get_route(task_type)
        candidates = [route["primary"]] + route["fallbacks"]

        attempted: list[str] = []
        last_error: Exception | None = None
        fallback_used = False
        fallback_reason: str | None = None

        with _safe_span(task_type) as span:
            span.set_attribute("llm.task_type", task_type)
            span.set_attribute("llm.message_count", len(messages))

            for i, model in enumerate(candidates):
                attempted.append(model)
                provider = extract_provider(model)

                log.debug(
                    "llm_attempt",
                    task_type=task_type,
                    model=model,
                    attempt=i + 1,
                    total_candidates=len(candidates),
                )

                t0 = time.monotonic()
                try:
                    response = await asyncio.wait_for(
                        litellm.acompletion(
                            model=model,
                            messages=messages,
                            max_tokens=max_tokens,
                            temperature=temperature,
                            **litellm_kwargs,
                        ),
                        timeout=self._timeout,
                    )

                    latency_ms = int((time.monotonic() - t0) * 1000)
                    prompt_tokens, completion_tokens = extract_usage_from_response(response)

                    # Determine status and fallback metadata
                    status = "FALLBACK_USED" if fallback_used else "SUCCESS"

                    # Record usage (fire-and-forget pattern — errors logged but not raised)
                    try:
                        await record_usage(
                            db,
                            model=model,
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            latency_ms=latency_ms,
                            status=status,
                            agent_exec_id=agent_exec_id,
                            event_id=event_id,
                            fallback_reason=fallback_reason,
                        )
                    except Exception as tracking_err:
                        log.warning(
                            "llm_usage_tracking_failed",
                            error=str(tracking_err),
                            model=model,
                        )

                    span.set_attribute("llm.model_used", model)
                    span.set_attribute("llm.provider", provider)
                    span.set_attribute("llm.total_tokens", prompt_tokens + completion_tokens)
                    span.set_attribute("llm.latency_ms", latency_ms)

                    log.info(
                        "llm_success",
                        task_type=task_type,
                        model=model,
                        provider=provider,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        latency_ms=latency_ms,
                        fallback_used=fallback_used,
                    )

                    return CompletionResult(
                        response=response,
                        model_used=model,
                        provider=provider,
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        latency_ms=latency_ms,
                        fallback_used=fallback_used,
                        fallback_reason=fallback_reason,
                    )

                except asyncio.TimeoutError as exc:
                    latency_ms = int((time.monotonic() - t0) * 1000)
                    last_error = exc
                    fallback_reason = f"Timeout after {self._timeout}s on {model}"
                    log.warning(
                        "llm_timeout",
                        model=model,
                        task_type=task_type,
                        timeout=self._timeout,
                    )

                except Exception as exc:
                    latency_ms = int((time.monotonic() - t0) * 1000)
                    last_error = exc
                    exc_str = str(exc).lower()
                    is_auth = any(
                        kw in exc_str
                        for kw in ("api key", "apikey", "authentication", "401", "403", "unauthorized")
                    )
                    fallback_reason = (
                        f"{'AuthError' if is_auth else type(exc).__name__} on {model}"
                    )
                    log.warning(
                        "llm_provider_error",
                        model=model,
                        task_type=task_type,
                        error_type=type(exc).__name__,
                        # Never log the full exception message — may contain key fragments
                        is_auth_error=is_auth,
                    )

                # Mark that we're now in fallback territory
                fallback_used = True

                # Record the failed attempt usage (0 tokens)
                try:
                    await record_usage(
                        db,
                        model=model,
                        prompt_tokens=0,
                        completion_tokens=0,
                        latency_ms=latency_ms,
                        status="TIMEOUT" if isinstance(last_error, asyncio.TimeoutError) else "ERROR",
                        agent_exec_id=agent_exec_id,
                        event_id=event_id,
                        fallback_reason=fallback_reason,
                    )
                except Exception:
                    pass  # don't block fallback loop on tracking failure

            # All candidates exhausted
            span.set_attribute("llm.all_failed", True)
            raise LLMGatewayError(
                task_type=task_type,
                attempted=attempted,
                last_error=last_error or RuntimeError("unknown"),
            )


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

# Module-level singleton — import and use directly in agents
_default_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """Return the module-level LLMClient singleton. Creates it on first call."""
    global _default_client
    if _default_client is None:
        _default_client = LLMClient()
    return _default_client
