"""
LLM Gateway — task-type to model routing table.

Maps each task type to a primary model and an ordered fallback list.
Agents call the gateway with a task_type; the gateway selects the model.

Model IDs use the exact LiteLLM provider prefix format:
  watsonx/<model>  → IBM watsonx.ai
  gemini/<model>   → Google Gemini (via generativeai)
  groq/<model>     → Groq-hosted open models

These strings are the source of truth — they must never be hardcoded elsewhere.
"""

from typing import TypedDict


class ModelRoute(TypedDict):
    primary: str
    fallbacks: list[str]


# Task type → model routing rules
# Fallback order: tried left-to-right when primary is unavailable or errors.
TASK_ROUTING: dict[str, ModelRoute] = {
    # Full reasoning + structured JSON plan (Planner Agent, Event Intelligence Agent)
    "strategic_reasoning": {
        "primary": "watsonx/ibm/granite-3-1-8b-instruct",
        "fallbacks": ["gemini/gemini-1.5-pro", "groq/llama-3.1-70b-versatile"],
    },
    # Structured JSON extraction from context (Egress Forecast, Supply, Police Agents)
    "structured_extraction": {
        "primary": "watsonx/ibm/granite-3-1-8b-instruct",
        "fallbacks": ["groq/llama-3.1-8b-instant", "gemini/gemini-1.5-flash"],
    },
    # Low-latency binary / categorical decisions (routing checks, label classification)
    "classification": {
        "primary": "groq/llama-3.1-8b-instant",
        "fallbacks": ["gemini/gemini-1.5-flash", "watsonx/ibm/granite-3-1-8b-instruct"],
    },
    # Multilingual text generation EN/KN/HI (Citizen Guidance Agent)
    "multilingual_generation": {
        "primary": "gemini/gemini-1.5-flash",
        "fallbacks": ["groq/llama-3.1-70b-versatile", "watsonx/ibm/granite-3-1-8b-instruct"],
    },
}

# All distinct model strings referenced above — used for health checks
ALL_MODELS: list[str] = [
    "watsonx/ibm/granite-3-1-8b-instruct",
    "gemini/gemini-1.5-flash",
    "gemini/gemini-1.5-pro",
    "groq/llama-3.1-8b-instant",
    "groq/llama-3.1-70b-versatile",
]

# Provider prefix → canonical short name (used in DB and logs)
PROVIDER_MAP: dict[str, str] = {
    "watsonx": "watsonx",
    "gemini":  "gemini",
    "groq":    "groq",
}


def get_route(task_type: str) -> ModelRoute:
    """Return primary + fallbacks for a task type. Raises ValueError for unknown types."""
    if task_type not in TASK_ROUTING:
        raise ValueError(
            f"Unknown task_type '{task_type}'. "
            f"Valid options: {list(TASK_ROUTING.keys())}"
        )
    return TASK_ROUTING[task_type]


def extract_provider(model: str) -> str:
    """Extract provider short name from LiteLLM model string.

    Examples:
        "watsonx/ibm/granite-3-1-8b-instruct" → "watsonx"
        "gemini/gemini-1.5-flash"              → "gemini"
        "groq/llama-3.1-8b-instant"            → "groq"
    """
    prefix = model.split("/")[0]
    return PROVIDER_MAP.get(prefix, prefix)
