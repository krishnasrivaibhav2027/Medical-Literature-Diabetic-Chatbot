import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select
from backend.core.database import AsyncSessionLocal
from backend.chatbot.models import DocumentChunk

logger = logging.getLogger("app.bm25")

_corpus: List[Dict[str, Any]] = []
_bm25: Optional[BM25Okapi] = None
_init_lock = asyncio.Lock()


async def get_bm25_index(force_reload: bool = False) -> Tuple[BM25Okapi, List[Dict[str, Any]]]:
    """
    Thread-safe lazy initializer for the BM25 sparse retrieval index.
    Loads documents from the PostgreSQL document_chunks table.
    """
    global _bm25, _corpus

    if _bm25 is not None and not force_reload:
        return _bm25, _corpus

    async with _init_lock:
        if _bm25 is not None and not force_reload:
            return _bm25, _corpus

        logger.info("Initializing BM25 index from PostgreSQL document_chunks...")
        async with AsyncSessionLocal() as session:
            stmt = select(
                DocumentChunk.id,
                DocumentChunk.content,
                DocumentChunk.metadata_json,
            )
            res = await session.execute(stmt)
            rows = res.fetchall()

        if not rows:
            logger.warning("No document chunks found in PostgreSQL. BM25 index is empty.")
            _corpus = []
            _bm25 = BM25Okapi([["empty"]])
            return _bm25, _corpus

        corpus_list = [
            {"id": row.id, "text": row.content, "metadata": row.metadata_json or {}}
            for row in rows
        ]

        tokenized_corpus = [doc["text"].lower().split() for doc in corpus_list]
        _bm25 = BM25Okapi(tokenized_corpus)
        _corpus = corpus_list
        logger.info("BM25 index built with %d documents.", len(_corpus))
        return _bm25, _corpus


async def retrieve_using_bm25(query: str, top_k: int = 50) -> list[dict]:
    """Retrieve top-k documents from the knowledge base using BM25."""
    tokenized_query = query.lower().split()
    if not tokenized_query:
        return []

    bm25, corpus = await get_bm25_index()
    if not corpus:
        return []

    scores = bm25.get_scores(tokenized_query)
    top_k = min(top_k, len(corpus))
    top_indices = np.argsort(scores)[-top_k:][::-1]
    return [corpus[i] for i in top_indices]


def invalidate_bm25_cache() -> None:
    """Clear BM25 cache so next query reloads updated documents from PostgreSQL."""
    global _bm25, _corpus
    _bm25 = None
    _corpus = []
    logger.info("BM25 index cache invalidated.")