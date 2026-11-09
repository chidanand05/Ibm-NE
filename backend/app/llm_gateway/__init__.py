"""
LLM Gateway public API.

Import from here in agents and API routes:

    from app.llm_gateway import LLMClient, LLMGatewayError, get_llm_client
    from app.llm_gateway import check_provider_health, get_provider_summary
    from app.llm_gateway.router import TASK_ROUTING, get_route
"""

from app.llm_gateway.client import (  # noqa: F401
    CompletionResult,
    LLMClient,
    LLMGatewayError,
    get_llm_client,
)
from app.llm_gateway.health import (  # noqa: F401
    check_provider_health,
    get_provider_summary,
)
from app.llm_gateway.router import (  # noqa: F401
    TASK_ROUTING,
    ALL_MODELS,
    extract_provider,
    get_route,
)
from app.llm_gateway.tracker import (  # noqa: F401
    record_usage,
    extract_usage_from_response,
)

__all__ = [
    # client
    "CompletionResult",
    "LLMClient",
    "LLMGatewayError",
    "get_llm_client",
    # health
    "check_provider_health",
    "get_provider_summary",
    # router
    "TASK_ROUTING",
    "ALL_MODELS",
    "extract_provider",
    "get_route",
    # tracker
    "record_usage",
    "extract_usage_from_response",
]
