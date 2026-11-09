"""
LLM Gateway — provider health checks.

Sends a minimal "Say OK" prompt to each configured provider.
Used by:
  - GET /health  (startup readiness)
  - GET /api/v1/llm/status  (operator dashboard)

Design rules:
  - Never log or return API key values.
  - If APIKEY is empty/unset → return "not_configured" immediately (no network call).
  - Any network or auth error → return "unavailable".
  - Timeout per provider: 10 seconds.
  - Results are independent — one failure does not abort the others.
"""

from __future__ import annotations

import asyncio

import structlog

from app.config import get_settings

log = structlog.get_logger(__name__)

ProviderStatus = str  # "healthy" | "unavailable" | "not_configured"

_HEALTH_PROMPT = [{"role": "user", "content": "Reply with exactly the word OK."}]
_HEALTH_TIMEOUT = 10  # seconds


async def _check_provider(model: str, *, timeout: int = _HEALTH_TIMEOUT) -> ProviderStatus:
    """
    Attempt a minimal completion against `model`.

    Returns "healthy", "unavailable", or "not_configured".
    Never raises — all errors are caught internally.
    """
    try:
        import litellm  # imported here to avoid import-time side effects

        response = await asyncio.wait_for(
            litellm.acompletion(
                model=model,
                messages=_HEALTH_PROMPT,
                max_tokens=5,
                temperature=0,
            ),
            timeout=timeout,
        )
        # Any non-exception response counts as healthy
        _ = response
        return "healthy"

    except asyncio.TimeoutError:
        log.warning("llm_health_timeout", model=model)
        return "unavailable"

    except Exception as exc:
        # Classify as not_configured vs. unavailable
        exc_str = str(exc).lower()
        if any(kw in exc_str for kw in ("api key", "apikey", "authentication", "401", "403", "unauthorized")):
            log.info("llm_health_not_configured", model=model, reason=type(exc).__name__)
            return "not_configured"
        log.warning("llm_health_unavailable", model=model, reason=type(exc).__name__)
        return "unavailable"


def _is_configured(provider: str) -> bool:
    """
    Return True if the provider's API key env var is non-empty.
    Short-circuits before making any network call.
    """
    settings = get_settings()
    match provider:
        case "watsonx":
            return bool(settings.watsonx_apikey)
        case "gemini":
            return bool(settings.gemini_api_key)
        case "groq":
            return bool(settings.groq_api_key)
        case _:
            return False


async def check_provider_health() -> dict[str, ProviderStatus]:
    """
    Check all three configured providers concurrently.

    Returns a dict:
        {
            "watsonx": "healthy" | "unavailable" | "not_configured",
            "gemini":  ...,
            "groq":    ...,
        }

    Providers with empty/unset API keys return "not_configured" immediately.
    All three checks run in parallel; total wall-clock time ≤ _HEALTH_TIMEOUT seconds.
    """
    providers = {
        "watsonx": "watsonx/ibm/granite-3-1-8b-instruct",
        "gemini":  "gemini/gemini-1.5-flash",
        "groq":    "groq/llama-3.1-8b-instant",
    }

    async def _check(name: str, model: str) -> tuple[str, ProviderStatus]:
        if not _is_configured(name):
            log.debug("llm_health_skipped", provider=name, reason="not_configured")
            return name, "not_configured"
        status = await _check_provider(model)
        return name, status

    results = await asyncio.gather(*[_check(n, m) for n, m in providers.items()])
    return dict(results)


async def get_provider_summary() -> dict[str, object]:
    """
    Return a safe, key-free summary of provider configuration for the API response.
    Never includes API key values.
    """
    settings = get_settings()
    return {
        "watsonx": {
            "configured": bool(settings.watsonx_apikey),
            "url":        settings.watsonx_url,
            "project_id_set": bool(settings.watsonx_project_id),
        },
        "gemini": {
            "configured": bool(settings.gemini_api_key),
        },
        "groq": {
            "configured": bool(settings.groq_api_key),
        },
    }
