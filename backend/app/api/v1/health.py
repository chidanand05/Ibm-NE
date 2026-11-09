"""Health check endpoint — includes LLM provider status."""

from fastapi import APIRouter

from app.llm_gateway.health import check_provider_health, get_provider_summary

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    """
    Service health check.

    Returns 200 when the API is running.
    Includes LLM provider reachability status — no API keys are exposed.

    Provider status values:
      healthy         — provider responded successfully
      unavailable     — provider is configured but not reachable
      not_configured  — API key env var is empty/unset (no network call made)
    """
    llm_providers = await check_provider_health()

    return {
        "status": "ok",
        "service": "namma-exodus-backend",
        "version": "0.1.0",
        "llm_providers": llm_providers,
    }
