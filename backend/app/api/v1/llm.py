"""
LLM Gateway status endpoints.

Exposes provider configuration and health information.
Never exposes API key values.
"""

from fastapi import APIRouter

from app.llm_gateway.health import check_provider_health, get_provider_summary
from app.llm_gateway.router import TASK_ROUTING, ALL_MODELS

router = APIRouter()


@router.get("/status")
async def llm_status() -> dict:
    """
    LLM provider status and configuration summary.

    Returns current health status for all configured providers
    plus the task-type routing table. No API keys are included.
    """
    provider_health = await check_provider_health()
    provider_config = await get_provider_summary()

    return {
        "providers": {
            name: {
                "health": provider_health.get(name, "not_configured"),
                **provider_config.get(name, {}),
            }
            for name in ("watsonx", "gemini", "groq")
        },
        "task_routing": {
            task: {
                "primary": route["primary"],
                "fallbacks": route["fallbacks"],
            }
            for task, route in TASK_ROUTING.items()
        },
        "all_models": ALL_MODELS,
        "note": "API keys are never returned by this endpoint.",
    }


@router.get("/models")
async def list_models() -> dict:
    """List all LiteLLM model strings configured in the gateway."""
    return {"models": ALL_MODELS}
