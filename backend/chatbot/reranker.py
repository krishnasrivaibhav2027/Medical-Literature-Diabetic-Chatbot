import logging
import httpx
from typing import List, Dict, Any
from backend.core.config import settings

logger = logging.getLogger("app.reranker")

async def reranker(query: str, documents: List[Dict[str, Any]], top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Rerank documents using Jina Serverless Reranker API based on query relevance.
    Falls back gracefully to RRF candidate order if the external API call fails.
    """
    if not documents:
        return []

    target_top_n = min(top_n, len(documents))

    if not getattr(settings, "JINA_API_KEY", None):
        logger.warning("JINA_API_KEY not configured; returning un-reranked top candidates.")
        return documents[:target_top_n]

    headers = {
        "Authorization": f"Bearer {settings.JINA_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": getattr(settings, "JINA_RERANKER_MODEL", "jina-reranker-v3.5"),
        "query": query,
        "documents": [doc["text"] for doc in documents],
        "top_n": target_top_n,
    }

    url = getattr(settings, "JINA_URL", "https://api.jina.ai/v1/rerank")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            res = await client.post(url, json=payload, headers=headers)
            if res.status_code == 200:
                data = res.json()
                results = data.get("results", [])
                ranked_docs = []
                for item in results:
                    orig_idx = item["index"]
                    doc = documents[orig_idx]
                    doc["rerank_score"] = float(item.get("relevance_score", 0.0))
                    ranked_docs.append(doc)

                logger.info(
                    "Jina Reranker successfully reranked %d documents into top %d.",
                    len(documents),
                    len(ranked_docs),
                )
                return ranked_docs
            else:
                logger.error("Jina Reranker API error [%d]: %s", res.status_code, res.text)
    except Exception as e:
        logger.warning("Jina Reranker API call failed (%s); falling back to RRF rank order.", e)

    # Graceful fallback: return top_n from original document list (already sorted by RRF)
    for doc in documents[:target_top_n]:
        if "rerank_score" not in doc:
            doc["rerank_score"] = doc.get("rrf_score", 0.5)
    return documents[:target_top_n]