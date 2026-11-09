"""
MCP Server 6 — Historical Events Server (in-process).

Reads from and writes to ChromaDB for RAG retrieval of past event patterns.
Write access (store_event_outcome) is restricted to the 'learning' agent.

ChromaDB connection
-------------------
Uses chromadb.AsyncHttpClient connecting to the chromadb Docker service.
The client is created lazily on first use and cached as a module-level
singleton to avoid re-connecting on every call.

Embedding model
---------------
sentence-transformers/all-MiniLM-L6-v2 (384-dim) — loaded once and cached.
In unit tests this is mocked to avoid loading the full model.

Promotion path: wrap each function in @mcp.tool() for Streamable HTTP MCP.
"""

from __future__ import annotations

import structlog

from app.mcp_servers.permissions import PermissionDeniedError

log = structlog.get_logger(__name__)

COLLECTION_NAME = "historical_events"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── Module-level singletons (lazy) ────────────────────────────────────────────

_chroma_client = None
_embedding_fn = None


def _get_chroma_client():
    """Return (or create) the ChromaDB async HTTP client singleton."""
    global _chroma_client
    if _chroma_client is None:
        import chromadb  # noqa: PLC0415
        from app.config import get_settings  # noqa: PLC0415
        settings = get_settings()
        _chroma_client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
    return _chroma_client


def _get_embedding_fn():
    """Return (or create) the sentence-transformers embedding function singleton."""
    global _embedding_fn
    if _embedding_fn is None:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction  # noqa: PLC0415
        _embedding_fn = SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
    return _embedding_fn


def _get_or_create_collection():
    """Return the historical_events ChromaDB collection, creating it if absent."""
    client = _get_chroma_client()
    ef = _get_embedding_fn()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"description": "Historical event outcomes for RAG retrieval"},
    )


# ── Public API ────────────────────────────────────────────────────────────────

def retrieve_similar_events(
    query: str,
    top_k: int = 3,
) -> list[dict]:
    """
    Vector similarity search over historical event outcomes.

    Parameters
    ----------
    query   Natural language description, e.g. "RCB match 40000 attendance".
    top_k   Number of results to return (default 3).

    Returns
    -------
    List of dicts with event metadata and similarity distance.
    Returns [] if ChromaDB is unreachable or collection is empty.
    """
    try:
        collection = _get_or_create_collection()
        results = collection.query(
            query_texts=[query],
            n_results=min(top_k, max(1, collection.count())),
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        log.warning("history_server.retrieve_failed", error=str(exc))
        return []

    docs = results.get("documents", [[]])[0]
    metas = results.get("metadatas", [[]])[0]
    dists = results.get("distances", [[]])[0]

    return [
        {
            "document": doc,
            "metadata": meta,
            "distance": dist,
        }
        for doc, meta, dist in zip(docs, metas, dists)
    ]


def get_event_outcome(event_id: str) -> dict | None:
    """
    Return stored outcome for `event_id` from ChromaDB.

    Parameters
    ----------
    event_id  The event UUID to look up.

    Returns
    -------
    Outcome dict with metadata, or None if not found.
    """
    try:
        collection = _get_or_create_collection()
        results = collection.get(ids=[event_id], include=["documents", "metadatas"])
    except Exception as exc:
        log.warning("history_server.get_outcome_failed", event_id=event_id, error=str(exc))
        return None

    docs = results.get("documents", [])
    metas = results.get("metadatas", [])
    if not docs:
        return None

    return {
        "event_id": event_id,
        "document": docs[0],
        "metadata": metas[0] if metas else {},
    }


def store_event_outcome(
    event_id: str,
    outcome: dict,
    calling_agent: str,
) -> str:
    """
    Store a post-event outcome in ChromaDB.

    WRITE RESTRICTED: only the 'learning' agent may call this function.
    Calling from any other agent raises PermissionDeniedError immediately,
    before any ChromaDB operation is attempted.

    Parameters
    ----------
    event_id       The event UUID.
    outcome        Outcome dict (arbitrary metadata — stored as metadata + document).
    calling_agent  Agent ID of the caller. Must be "learning".

    Returns
    -------
    The ChromaDB document ID (== event_id).

    Raises
    ------
    PermissionDeniedError  If calling_agent != "learning".
    """
    if calling_agent != "learning":
        raise PermissionDeniedError(
            agent_id=calling_agent,
            tool_name="history_server.store_event_outcome",
        )

    # Build document text for embedding
    document = (
        f"Event: {outcome.get('event_name', 'Unknown')}. "
        f"Attendance: {outcome.get('actual_attendance', 'unknown')}. "
        f"Exit duration: {outcome.get('actual_exit_duration_mins', 'unknown')} minutes. "
        f"Transport adequacy: {outcome.get('transport_adequacy', 'unknown')}. "
        f"Lessons: {outcome.get('lessons_learned', 'none')}."
    )

    metadata = {
        "event_id": event_id,
        "data_source": "SIMULATED",
        **{k: str(v) for k, v in outcome.items() if isinstance(v, (str, int, float, bool))},
    }

    try:
        collection = _get_or_create_collection()
        # upsert so re-running the learning agent is idempotent
        collection.upsert(
            ids=[event_id],
            documents=[document],
            metadatas=[metadata],
        )
        log.info("history_server.stored", event_id=event_id, agent=calling_agent)
    except Exception as exc:
        log.error("history_server.store_failed", event_id=event_id, error=str(exc))
        raise

    return event_id


def reset_singletons_for_testing() -> None:
    """
    Reset module-level singletons.
    Call this in test teardown when mocking ChromaDB or the embedding function.
    """
    global _chroma_client, _embedding_fn
    _chroma_client = None
    _embedding_fn = None
