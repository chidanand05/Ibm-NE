"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from app.api.v1 import (
    agents,
    approvals,
    audit,
    auth,
    events,
    forecasts,
    guidance,
    health,
    llm,
    map_data,
    replay,
    transport,
    ws,
)
from app.config import get_settings
from app.observability.logging import configure_logging
from app.observability.tracing import init_tracing

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle events."""
    configure_logging()
    init_tracing()
    yield
    # Cleanup on shutdown (future: close DB pool, flush OTel spans)


def create_app() -> FastAPI:
    app = FastAPI(
        title="Namma Exodus API",
        description=(
            "Agentic AI-powered crowd-exit prediction and multi-modal "
            "transport coordination system for Bengaluru."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────────────
    app.include_router(health.router, tags=["health"])
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(events.router, prefix="/api/v1/events", tags=["events"])
    app.include_router(forecasts.router, prefix="/api/v1/forecasts", tags=["forecasts"])
    app.include_router(transport.router, prefix="/api/v1/transport", tags=["transport"])
    app.include_router(agents.router, prefix="/api/v1/agents", tags=["agents"])
    app.include_router(approvals.router, prefix="/api/v1/approvals", tags=["approvals"])
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    app.include_router(llm.router, prefix="/api/v1/llm", tags=["llm"])
    app.include_router(map_data.router, prefix="/api/v1/map", tags=["map"])
    app.include_router(guidance.router, prefix="/api/v1/guidance", tags=["guidance"])
    app.include_router(replay.router, prefix="/api/v1/replay", tags=["replay"])
    app.include_router(ws.router, prefix="/ws", tags=["websocket"])

    # ── OpenTelemetry instrumentation ─────────────────────────────────────────
    FastAPIInstrumentor.instrument_app(app)

    return app


app = create_app()
