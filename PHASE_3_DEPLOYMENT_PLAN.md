# 🚀 Phase 3: Production Deployment & Infrastructure Implementation Plan

This implementation plan details the deployment of the **Medical Literature Assistant (Hybrid RAG)** to production. It covers deploying the containerized FastAPI backend to **Google Cloud Run**, hosting the React SPA on **Vercel**, and configuring managed cloud services (**Cloud PostgreSQL + pgvector** and **Upstash Redis**).

---

## 🏗️ 1. Architecture Topology

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              PRODUCTION INFRASTRUCTURE                                 │
└────────────────────────────────────────────────────────────────────────────────────────┘

    [ End Users / Browsers ]
               │
               ▼ HTTPS
    ┌─────────────────────────┐
    │     Vercel Frontend     │  (React 19 + Vite 8 SPA)
    │  - Strict Route Guard   │  - Client BYOK Credential Vault (localStorage)
    │  - 403 Forbidden Page   │  - Dynamic Header Injection (x-llm-*, x-jina-*)
    └──────────┬──────────────┘
               │
               ▼ REST / Server-Sent Events (SSE) [HTTPS]
    ┌─────────────────────────────────────────────────────────┐
    │              Google Cloud Run (Serverless)               │
    │  - FastAPI Backend (Uvicorn ASGI Worker)                │
    │  - Pre-cached Embedding Gemma 300M Model (HF_HOME)      │
    │  - LangGraph State Machine (Tiktoken Tracker)           │
    │  - Autoscaling: 0 to 10 instances (Scale to Zero)       │
    │  - Hardware: 2 vCPU / 2 GiB RAM / 80 Concurrency        │
    └──────────┬─────────────────────────────┬────────────────┘
               │                             │
               ▼ Async Pool (TLS)            ▼ REST API (TLS)
    ┌─────────────────────────┐   ┌───────────────────────────┐
    │    Managed PostgreSQL   │   │    Upstash Redis Cache    │
    │       + pgvector        │   │  - Precomputed QA Cache   │
    │  - HNSW Vector Index    │   │  - Semantic Similarity    │
    │  - Row-Level Security   │   │  - Stream Token Buffer    │
    │  - Users & Threads DB   │   │  - API Rate Limiter       │
    └─────────────────────────┘   └───────────────────────────┘
               │                             │
               ▼                             ▼
    ┌─────────────────────────┐   ┌───────────────────────────┐
    │  Jina AI Reranker v3.5  │   │  LangSmith Observability  │
    │  (External Serverless)  │   │     (Cloud Tracing)       │
    └─────────────────────────┘   └───────────────────────────┘
```

---

## 📋 2. Prerequisites & Preparation

Before beginning deployment, ensure you have:
1. **Google Cloud Platform (GCP)** Account with billing enabled and `gcloud` CLI installed.
2. **Vercel** Account with GitHub integration or Vercel CLI installed.
3. **Managed PostgreSQL** instance (e.g., Supabase, Neon, or GCP Cloud SQL) with `vector` extension available.
4. **Upstash Redis** Database (Serverless Redis REST API).
5. **Git Repository** up to date with Phase 1 & 2 changes.

---

## 🛠️ 3. Step-by-Step Implementation Sequence

### Step 1: Provision Cloud Database & Initialize RLS

1. **Select a Managed PostgreSQL Provider**:
   - **Supabase** (Recommended: Free tier, built-in PgBouncer pooling, native pgvector support).
   - **Neon Serverless Postgres** (Scale-to-zero compute, native pgvector).
   - **Google Cloud SQL for PostgreSQL** (VPC peering, single-cloud IAM).

2. **Enable Vector Extension**:
   Run in your SQL query editor / console:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

3. **Run Database Migrations & Ingestion**:
   In your local shell, point `DATABASE_URL` to your cloud database connection string:
   ```powershell
   $env:DATABASE_URL="postgresql+asyncpg://<USER>:<PASSWORD>@<HOST>:5432/postgres?ssl=require"
   
   # Run the document ingestion pipeline to generate pgvector embeddings
   python -m backend.ingestion_pipeline.ingestion

   # Seed precomputed clinical Q&A embeddings into Redis & Database
   python -m backend.scripts.seed_precomputed_qa

   # Enable PostgreSQL Row-Level Security (RLS) on chat_threads and chat_messages
   python -m backend.scripts.enable_rls
   ```

---

### Step 2: Upstash Redis Configuration

1. Visit [Upstash Console](https://console.upstash.com/) and verify your Redis database:
   - Ensure **TLS (SSL)** is active.
   - Set max memory policy to `allkeys-lru` or `volatile-lru`.
2. Retrieve the connection credentials:
   - `UPSTASH_REDIS_REST_URL` (e.g., `https://xxxx-xxxxx.upstash.io`)
   - `UPSTASH_REDIS_REST_TOKEN` (e.g., `AXxxASQg...`)

> **Note on Shared Cache**: A centralized Redis instance guarantees that precomputed clinical FAQs and semantic cache hits serve responses in `< 50ms` for all authenticated users, while preserving user session isolation.

---

### Step 3: Hardened Dockerfile Optimization

To prevent 600MB model downloads during Cloud Run cold boots, update [Dockerfile](file:///d:/GitRepos/Hybrid_RAG/Dockerfile) with `HF_HOME=/app/model_cache` and ensure proper directory ownership for the non-root `appuser`:

```dockerfile
# syntax=docker/dockerfile:1
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    HF_HOME=/app/model_cache \
    PORT=8080

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r /app/backend/requirements.txt

# Pre-download Gemma 300M weights into /app/model_cache during build
RUN mkdir -p /app/model_cache && \
    python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('google/embeddinggemma-300m')"

COPY backend /app/backend

# Create non-root system user and assign directory permissions
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8080

CMD exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
```

---

### Step 4: Build & Deploy Backend on Google Cloud Run

#### 1. Configure GCP Project & Enable APIs:
```bash
gcloud auth login
gcloud config set project <YOUR-GCP-PROJECT-ID>

# Enable required Google Cloud services
gcloud services enable \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com
```

#### 2. Create Artifact Registry Repository:
```bash
gcloud artifacts repositories create hybrid-rag-repo \
  --repository-format=docker \
  --location=us-central1 \
  --description="Production repository for Hybrid RAG Assistant"
```

#### 3. Build & Push Image via Cloud Build:
```bash
gcloud builds submit --tag us-central1-docker.pkg.dev/<YOUR-GCP-PROJECT-ID>/hybrid-rag-repo/backend:v1 .
```

#### 4. Deploy Cloud Run Service:
```bash
gcloud run deploy hybrid-rag-backend \
  --image us-central1-docker.pkg.dev/<YOUR-GCP-PROJECT-ID>/hybrid-rag-repo/backend:v1 \
  --platform managed \
  --region us-central1 \
  --memory 2Gi \
  --cpu 2 \
  --min-instances 0 \
  --max-instances 10 \
  --concurrency 80 \
  --timeout 120s \
  --allow-unauthenticated \
  --set-env-vars "\
ENVIRONMENT=production,\
DEBUG=False,\
DATABASE_URL=postgresql+asyncpg://<USER>:<PASS>@<HOST>:5432/postgres?ssl=require,\
UPSTASH_REDIS_REST_URL=https://<YOUR-UPSTASH-INSTANCE>.upstash.io,\
UPSTASH_REDIS_REST_TOKEN=<YOUR-UPSTASH-TOKEN>,\
SECRET_KEY=<GENERATED-SECURE-JWT-SECRET>,\
ACCESS_TOKEN_EXPIRE_MINUTES=90,\
ALLOWED_ORIGINS=[\"https://<YOUR-FRONTEND-URL>.vercel.app\",\"http://localhost:5173\"],\
XKIRO_API_KEY=<DEFAULT-FALLBACK-KEY>,\
JINA_API_KEY=<DEFAULT-JINA-KEY>,\
LANGCHAIN_TRACING_V2=true,\
LANGCHAIN_API_KEY=<LANGSMITH-API-KEY>,\
LANGCHAIN_PROJECT=Medical-Literature-RAG-Assistant-production"
```

> **Deployed Backend URL**: Once deployed, GCP outputs the public HTTPS endpoint:
> `https://hybrid-rag-backend-xxxxxxxxxx-uc.a.run.app`

---

### Step 5: Deploy Frontend on Vercel

1. **Create Vercel SPA Routing Configuration**:
   Create [frontend/vercel.json](file:///d:/GitRepos/Hybrid_RAG/frontend/vercel.json) to handle single-page application client routing:
   ```json
   {
     "rewrites": [
       { "source": "/(.*)", "destination": "/index.html" }
     ]
   }
   ```

2. **Deploy via Vercel CLI or GitHub Integration**:
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Vite`
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`

3. **Configure Frontend Environment Variable**:
   In the Vercel Project Settings under **Environment Variables**:
   ```ini
   VITE_API_URL=https://hybrid-rag-backend-xxxxxxxxxx-uc.a.run.app
   ```

4. **Trigger Deployment**:
   ```bash
   cd frontend
   vercel --prod
   ```

---

### Step 6: Synchronize CORS Origin Settings

Update the backend Cloud Run service with the exact production frontend Vercel URL to avoid CORS cross-origin blocks:

```bash
gcloud run services update hybrid-rag-backend \
  --region us-central1 \
  --update-env-vars ALLOWED_ORIGINS="[\"https://medical-rag-assistant.vercel.app\",\"http://localhost:5173\"]"
```

---

## 🧪 4. Post-Deployment Verification & Smoke Tests

| Test Case | Execution Steps | Expected Outcome | Status |
| :--- | :--- | :--- | :---: |
| **1. Health Check** | `curl -I https://<BACKEND-URL>/health` | HTTP 200 `{"status": "ok"}` | ⬜ |
| **2. Auth Route Guard** | Visit frontend directly in Incognito mode without logging in | Immediate 403 Forbidden screen (`Access Denied`) | ⬜ |
| **3. Clinical Sign-Up / Login** | Click "Go to Login", register new user, log in | JWT token stored, chat interface rendered | ⬜ |
| **4. Thread & Message Isolation** | Create chat thread under User A; attempt access from User B | HTTP 403 Forbidden / RLS filter enforced | ⬜ |
| **5. BYOK LLM Execution** | Enter custom OpenAI/Groq API key & model in Settings modal; submit query | Backend routes query through user's BYOK provider | ⬜ |
| **6. BYOK Jina Reranker** | Enter custom Jina API key in Settings modal; submit RAG query | Jina reranker runs with user key | ⬜ |
| **7. Semantic Cache Speed** | Ask `"What are the diagnosis criteria for Type 2 Diabetes?"` twice | 2nd response arrives in `< 50ms` (Cache Hit badge displayed) | ⬜ |
| **8. Observability Trace** | Check LangSmith Dashboard project runs | Visual trace shows LangGraph execution nodes and token count | ⬜ |

---

## 🔒 5. Production Security Verification

- [x] **No Secrets in Source Control:** `.env` is ignored by `.gitignore`. Template provided in `backend/.env.example`.
- [x] **Row-Level Security (RLS):** `chat_threads` and `chat_messages` are strictly scoped by user ID.
- [x] **Client-Side Secret Isolation:** BYOK keys are held strictly in the user's browser localStorage and sent over TLS headers per request; they are never persisted to the backend database.
- [x] **Least-Privilege Docker Execution:** Container runs under unprivileged user `appuser` (UID 1000).
- [x] **Zero Cold-Boot Model Fetch:** HuggingFace embedding weights are embedded inside image `/app/model_cache`.
