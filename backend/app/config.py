"""Application settings loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000"

    # ── Database ─────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://namma:changeme@postgres:5432/namma_exodus"
    alembic_database_url: str = "postgresql+psycopg2://namma:changeme@postgres:5432/namma_exodus"

    # ── Redis ────────────────────────────────────────────────────────────────
    redis_url: str = "redis://redis:6379/0"

    # ── ChromaDB ─────────────────────────────────────────────────────────────
    chromadb_host: str = "chromadb"
    chromadb_port: int = 8000

    # ── MCP Servers ──────────────────────────────────────────────────────────
    crowd_sim_mcp_url: str = "http://crowd-sim-mcp:8001/mcp"

    # ── JWT ──────────────────────────────────────────────────────────────────
    jwt_secret: str = "changeme-insecure-dev-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480

    # ── IBM watsonx.ai ───────────────────────────────────────────────────────
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"
    watsonx_apikey: str = ""
    watsonx_project_id: str = ""

    # ── Google Gemini ────────────────────────────────────────────────────────
    gemini_api_key: str = ""

    # ── Groq ─────────────────────────────────────────────────────────────────
    groq_api_key: str = ""

    # ── OpenTelemetry ────────────────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = "http://jaeger:4317"
    otel_service_name: str = "namma-exodus-backend"

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse comma-separated CORS_ORIGINS string into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def chromadb_url(self) -> str:
        return f"http://{self.chromadb_host}:{self.chromadb_port}"


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance. Use as a FastAPI dependency."""
    return Settings()
