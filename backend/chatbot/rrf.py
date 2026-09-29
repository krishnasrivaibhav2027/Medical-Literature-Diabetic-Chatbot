async def rrf_score(ranked_lists: list[list[dict]], k: int = 60, top_k: int = 50) -> list[dict]:
    """Fuse multiple ranked document lists using Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    doc_map: dict[str, dict] = {}

    for ranked_list in ranked_lists:
        for rank, doc in enumerate(ranked_list):
            doc_id = doc["id"] if isinstance(doc, dict) else str(doc)
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))
            if doc_id not in doc_map:
                doc_map[doc_id] = doc if isinstance(doc, dict) else {"id": doc_id, "text": str(doc), "metadata": {}}

    sorted_ids = sorted(scores, key=scores.get, reverse=True)
    return [doc_map[doc_id] for doc_id in sorted_ids[:top_k]]