"""
LLM Gateway — per-request token and cost tracking.

Writes one LLMUsage row to the database for every LLM call.
Extracts token counts and latency from the LiteLLM response object.

Cost estimates are approximate and based on publicly available pricing
at the time of implementation. They are stored as ESTIMATED values only.
Never use these figures for billing.
"""

from __future__ import annotations

import time
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from app.llm_gateway.router import extract_provider

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from app.models.db.llm_usage import LLMUsage

log = structlog.get_logger(__name__)

# ── Approximate cost per 1 000 tokens (USD) ──────────────────────────────────
# Rates are indicative only; update when providers change pricing.
# Source: provider pricing pages as of 2026-11.
_COST_PER_1K: dict[str, float] = {
    "watsonx/ibm/granite-3-1-8b-instruct": 0.001_00,   # estimate — IBM Lite tier
    "gemini/gemini-1.5-flash":             0.000_075,
    "gemini/gemini-1.5-pro":               0.001_25,
    "groq/llama-3.1-8b-instant":           0.000_10,
    "groq/llama-3.1-70b-versatile":        0.000_59,
}


def _estimate_cost(model: str, total_tokens: int) -> Decimal:
    """Return estimated USD cost for a call. Returns 0 for unknown models."""
    rate = _COST_PER_1K.get(model, 0.0)
    return Decimal(str(round(rate * total_tokens / 1000, 6)))


async def record_usage(
    db: AsyncSession,
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    status: str = "SUCCESS",
    agent_exec_id: str | None = None,
    event_id: str | None = None,
    fallback_reason: str | None = None,
) -> LLMUsage:
    """
    Persist one LLMUsage row.

    Parameters
    ----------
    db              Async SQLAlchemy session (from FastAPI dependency or direct call).
    model           LiteLLM model string, e.g. "groq/llama-3.1-8b-instant".
    prompt_tokens   Input token count from LiteLLM response.
    completion_tokens  Output token count from LiteLLM response.
    latency_ms      Wall-clock time for the LLM call in milliseconds.
    status          "SUCCESS" | "ERROR" | "TIMEOUT" | "FALLBACK_USED".
    agent_exec_id   FK to agent_executions.id — may be None for health-check calls.
    event_id        FK to events.id — may be None.
    fallback_reason Human-readable reason when a fallback model was used.

    Returns
    -------
    The persisted LLMUsage instance.
    """
    # Import here (not at module level) to avoid pulling geoalchemy2/full ORM
    # stack into unit test environments that don't have PostGIS installed.
    from app.models.db.llm_usage import LLMUsage  # noqa: PLC0415

    total_tokens = prompt_tokens + completion_tokens
    provider = extract_provider(model)
    cost = _estimate_cost(model, total_tokens)

    record = LLMUsage(
        agent_exec_id=agent_exec_id,
        event_id=event_id,
        model=model,
        provider=provider,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=cost,
        latency_ms=latency_ms,
        status=status,
        fallback_reason=fallback_reason,
    )

    db.add(record)
    await db.flush()  # get the auto-assigned id without committing

    log.debug(
        "llm_usage_recorded",
        model=model,
        provider=provider,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=float(cost),
        latency_ms=latency_ms,
        status=status,
    )

    return record


def extract_usage_from_response(response: object) -> tuple[int, int]:
    """
    Extract (prompt_tokens, completion_tokens) from a LiteLLM ModelResponse.

    LiteLLM guarantees a `usage` attribute with `prompt_tokens` and
    `completion_tokens` on successful responses. Falls back to 0 on any
    attribute error (e.g., streaming responses or mocked objects in tests).
    """
    try:
        usage = getattr(response, "usage", None)
        if usage is None:
            return 0, 0
        pt = getattr(usage, "prompt_tokens", 0) or 0
        ct = getattr(usage, "completion_tokens", 0) or 0
        return int(pt), int(ct)
    except Exception:
        return 0, 0
