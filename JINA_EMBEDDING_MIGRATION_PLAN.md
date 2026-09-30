# Jina Embeddings v3 Migration Plan

A concise, step-by-step implementation guide to switch from the local `google/embeddinggemma-300m` model to the serverless **Jina Embeddings v3 API** (`dimensions=768`).

---

## Why This Solves the Railway Crash
* **Memory Drop**: Container RAM drops from ~1.1GB to **< 90MB**, running smoothly inside Railway's 512MB free tier limit.
* **No Schema Migration**: `jina-embeddings-v3` outputs **768 dimensions**, perfectly matching Supabase `document_chunks.embedding Vector(768)` and the existing PostgreSQL HNSW index.
* **Fast Re-Ingestion**: Re-embedding all 89 PDFs in `backend/knowledge_base/` takes **~30 to 45 seconds**.

---

## Migration Checklist

### Step 1: Verify Environment Variables
Ensure these lines exist in [`backend/.env`](file:///d:/GitRepos/Hybrid_RAG/backend/.env):
```env
JINA_API_KEY=your_jina_api_key_here
JINA_EMBEDDING_MODEL=jina-embeddings-v3
JINA_EMBEDDING_URL=https://api.jina.ai/v1/embeddings
```
*(Also add `JINA_EMBEDDING_MODEL` and `JINA_EMBEDDING_URL` to Railway Variables).*

---

### Step 2: Delete Old Gemma Embeddings from Supabase
Run the dedicated deletion script from your PowerShell terminal:
```powershell
python -m backend.scripts.delete_ingested_chunks
```
> **Alternative**: Run `TRUNCATE TABLE document_chunks;` directly in the Supabase SQL Editor.

---

### Step 3: Re-Ingest Knowledge Base with Jina API
Run the core ingestion pipeline (now powered by Jina Embeddings v3 768d):
```powershell
python -m backend.ingestion_pipeline.ingestion
```
*Time taken: ~30 to 45 seconds for all 89 PDFs.*

---

### Step 4: Re-Seed Precomputed Q&A Table
Re-embed the clinical FAQ dataset so semantic cache matches the new Jina latent space:
```powershell
python -m backend.scripts.seed_precomputed_qa --force
```

---

### Step 5: Wire the Jina Embedder into the Application Code

Make these 2 quick changes in your project:

#### 1. [`backend/chatbot/hybrid_workflow.py`](file:///d:/GitRepos/Hybrid_RAG/backend/chatbot/hybrid_workflow.py)
Replace `get_embedding_model()` (lines 61-68) with:
```python
from backend.chatbot.jina_embedder import get_jina_embedder

def get_embedding_model():
    """Returns the lightweight JinaEmbedder client (768d)."""
    return get_jina_embedder()
```

#### 2. [`backend/main.py`](file:///d:/GitRepos/Hybrid_RAG/backend/main.py)
In `prewarm_models()` (around line 45), replace the PyTorch warmup with a lightweight API ping:
```python
    embedder = get_embedding_model()
    test_emb = await asyncio.to_thread(embedder.encode, "ping", task="retrieval.query")
    logger.info("Jina Embeddings API ready (verified %d-dim vector).", len(test_emb))
```

---

### Step 6: Test Locally & Deploy

1. **Test Backend Locally**:
   ```powershell
   python run_backend.py
   ```
   *Logs should show startup in ~1.5 seconds without any PyTorch memory allocation.*

2. **Commit and Push to Railway**:
   ```powershell
   git add .
   git commit -m "feat(rag): migrate to serverless Jina Embeddings v3 (768d)"
   git push origin production
   ```

3. **Verify Railway Dashboard**:
   * Build finishes in ~30 seconds.
   * Service memory stabilizes at **~80MB RAM**.
   * Healthcheck `/health` returns `200 OK`.
