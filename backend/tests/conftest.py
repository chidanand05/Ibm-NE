"""
Conftest for the backend test suite.

Installs mock stubs for packages that are only available inside the Docker
container (geoalchemy2, asyncpg, opentelemetry-exporter-otlp-proto-grpc)
so that unit tests can import app modules without those packages installed
in the local Python environment.

This conftest is automatically loaded by pytest for every test run.
"""

from __future__ import annotations

import sys
import types


def _stub_module(name: str, **attrs) -> types.ModuleType:
    """Create and register a minimal stub module."""
    mod = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(mod, k, v)
    sys.modules[name] = mod
    return mod


# ── geoalchemy2 ───────────────────────────────────────────────────────────────
# Only stub if not already installed.
if "geoalchemy2" not in sys.modules:
    # Geography must be a proper SQLAlchemy TypeEngine subclass so that
    # mapped_column(Geography(...)) doesn't raise ArgumentError.
    from sqlalchemy.sql import sqltypes as _sqltypes

    class _Geography(_sqltypes.TypeEngine):
        """Minimal stub for geoalchemy2.Geography used by Venue.location column."""

        def __init__(self, geometry_type: str = "GEOMETRY", srid: int = 4326, **kwargs):
            self.geometry_type = geometry_type
            self.srid = srid

    geo_mod = _stub_module("geoalchemy2", Geography=_Geography)
    _stub_module("geoalchemy2.types", Geography=_Geography)


# ── asyncpg ───────────────────────────────────────────────────────────────────
if "asyncpg" not in sys.modules:
    _stub_module("asyncpg")


# ── redis ─────────────────────────────────────────────────────────────────────
# redis.asyncio is only used inside the Docker container.
if "redis" not in sys.modules:
    redis_mod = _stub_module("redis")
    redis_asyncio_mod = _stub_module("redis.asyncio")

    class _FakeRedis:
        """Minimal stub for redis.asyncio.Redis used in dependencies.py."""
        @staticmethod
        def from_url(*args, **kwargs) -> "_FakeRedis":
            return _FakeRedis()

    redis_asyncio_mod.Redis = _FakeRedis
    redis_asyncio_mod.from_url = _FakeRedis.from_url


# ── opentelemetry-exporter-otlp-proto-grpc ───────────────────────────────────
# The OTel exporter sub-packages are only needed by tracing.py at runtime
# inside Docker (Jaeger is not available locally).  Stub them so that the
# app.observability.tracing module can be imported without crashing.
_otlp_exporter_path = "opentelemetry.exporter.otlp.proto.grpc.trace_exporter"
if _otlp_exporter_path not in sys.modules:
    class _OTLPSpanExporter:
        def __init__(self, *args, **kwargs):
            pass

    _stub_module(_otlp_exporter_path, OTLPSpanExporter=_OTLPSpanExporter)

    # Parent path stubs (must exist for the sub-module import to work)
    for _path in [
        "opentelemetry.exporter.otlp",
        "opentelemetry.exporter.otlp.proto",
        "opentelemetry.exporter.otlp.proto.grpc",
    ]:
        if _path not in sys.modules:
            _stub_module(_path)


# ── langgraph ─────────────────────────────────────────────────────────────────
# LangGraph is only available inside Docker. Stub it for local unit tests.
if "langgraph" not in sys.modules:
    import asyncio as _asyncio

    # ── langgraph.graph ─────────────────────────────────────────────────────
    _END = "__end__"

    class _StateGraph:
        """Minimal stub for langgraph.graph.StateGraph."""
        def __init__(self, state_schema=None): self._nodes = {}; self._edges = []; self._entry = None
        def add_node(self, name, fn): self._nodes[name] = fn
        def set_entry_point(self, name): self._entry = name
        def add_edge(self, a, b): pass
        def add_conditional_edges(self, src, fn, mapping=None): pass
        def compile(self, checkpointer=None, interrupt_before=None):
            return _CompiledGraph(self._nodes)

    class _CompiledGraph:
        def __init__(self, nodes): self._nodes = nodes
        async def ainvoke(self, state, config=None): return state if isinstance(state, dict) else {}
        async def aget_state(self, config=None): return None

    _lg_graph_mod = _stub_module(
        "langgraph.graph",
        StateGraph=_StateGraph,
        END=_END,
    )
    _stub_module("langgraph", graph=_lg_graph_mod)

    # ── langgraph.types ─────────────────────────────────────────────────────
    class _Command:
        """Minimal stub for langgraph.types.Command."""
        def __init__(self, resume=None, goto=None, update=None):
            self.resume = resume
            self.goto = goto
            self.update = update or {}

    def _interrupt(value=None):
        """Minimal stub for langgraph.types.interrupt."""
        return value

    _stub_module("langgraph.types", Command=_Command, interrupt=_interrupt)

    # ── langgraph.checkpoint.memory ─────────────────────────────────────────
    class _MemorySaver:
        def __init__(self): pass
        async def setup(self): pass

    _stub_module("langgraph.checkpoint.memory", MemorySaver=_MemorySaver)

    # ── langgraph.checkpoint.postgres.aio ───────────────────────────────────
    class _AsyncPostgresSaver:
        def __init__(self): pass
        @classmethod
        def from_conn_string(cls, conn_string): return cls()
        async def setup(self): pass

    _stub_module(
        "langgraph.checkpoint.postgres.aio",
        AsyncPostgresSaver=_AsyncPostgresSaver,
    )
    _stub_module("langgraph.checkpoint", MemorySaver=_MemorySaver)
    _stub_module("langgraph.checkpoint.postgres", AsyncPostgresSaver=_AsyncPostgresSaver)

