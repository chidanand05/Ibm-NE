"""ChromaDB historical event seed — 3 synthetic records."""

from __future__ import annotations

import structlog

from app.seed.constants import CHROMA_HISTORICAL_RECORDS

log = structlog.get_logger(__name__)

COLLECTION_NAME = "historical_events"


async def seed_chroma_history() -> None:
    """
    Upsert 3 synthetic historical event records into ChromaDB.

    Uses upsert so re-running is idempotent.
    Requires chromadb Docker service to be running.
    """
    import chromadb  # noqa: PLC0415
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction  # noqa: PLC0415
    from app.config import get_settings  # noqa: PLC0415

    settings = get_settings()
    client = chromadb.HttpClient(
        host=settings.chromadb_host,
        port=settings.chromadb_port,
    )
    ef = SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"description": "Historical event outcomes for RAG retrieval — SIMULATED"},
    )

    ids       = [r["id"]       for r in CHROMA_HISTORICAL_RECORDS]
    documents = [r["document"] for r in CHROMA_HISTORICAL_RECORDS]
    metadatas = [r["metadata"] for r in CHROMA_HISTORICAL_RECORDS]

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    log.info("seed.chroma_upserted", count=len(CHROMA_HISTORICAL_RECORDS))
