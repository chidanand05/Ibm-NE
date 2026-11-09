"""Custom metrics placeholder — populated in Milestone 6."""


def record_agent_latency(agent_id: str, duration_ms: int) -> None:
    """Record agent execution latency. Wired to OpenTelemetry metrics in M6."""
    pass


def record_llm_tokens(provider: str, model: str, tokens: int) -> None:
    """Record LLM token consumption. Wired to Prometheus gauge in M6."""
    pass
