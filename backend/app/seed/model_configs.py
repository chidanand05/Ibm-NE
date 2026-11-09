"""Model config seed — prompt templates for all 7 agents."""

from __future__ import annotations

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.seed.constants import AGENT_PROMPT_TEMPLATES

log = structlog.get_logger(__name__)

# Agent ID → (task_type, model_name, provider, temperature, max_tokens)
_AGENT_MODEL_MAP = {
    "event_intelligence": ("structured_extraction",  "watsonx/ibm/granite-3-1-8b-instruct", "watsonx", "0.1", 2048),
    "egress_forecast":    ("structured_extraction",  "watsonx/ibm/granite-3-1-8b-instruct", "watsonx", "0.1", 2048),
    "supply":             ("classification",          "groq/llama-3.1-8b-instant",            "groq",    "0.1", 2048),
    "police_coordination":("structured_extraction",  "watsonx/ibm/granite-3-1-8b-instruct", "watsonx", "0.1", 2048),
    "planner":            ("strategic_reasoning",     "watsonx/ibm/granite-3-1-8b-instruct", "watsonx", "0.2", 4096),
    "citizen_guidance":   ("multilingual_generation", "gemini/gemini-1.5-flash",              "gemini",  "0.3", 2048),
    "learning":           ("structured_extraction",   "groq/llama-3.1-8b-instant",            "groq",    "0.1", 2048),
}


async def seed_model_configs(db: AsyncSession) -> None:
    """Insert model configs for all 7 agents. Idempotent."""
    stmt = text("""
        INSERT INTO model_configs (
            id, agent_id, task_type, model_name, provider,
            prompt_template, prompt_version,
            temperature, max_tokens, is_active, created_at
        )
        VALUES (
            gen_random_uuid(),
            :agent_id, :task_type, :model_name, :provider,
            :prompt_template, :prompt_version,
            :temperature, :max_tokens, TRUE, NOW()
        )
        ON CONFLICT (agent_id, task_type, prompt_version) DO NOTHING
    """)

    for agent_id, (task_type, model_name, provider, temperature, max_tokens) in _AGENT_MODEL_MAP.items():
        await db.execute(stmt, {
            "agent_id":        agent_id,
            "task_type":       task_type,
            "model_name":      model_name,
            "provider":        provider,
            "prompt_template": AGENT_PROMPT_TEMPLATES[agent_id],
            "prompt_version":  "v1.0",
            "temperature":     temperature,
            "max_tokens":      max_tokens,
        })

    log.info("seed.model_configs_upserted", count=len(_AGENT_MODEL_MAP))
