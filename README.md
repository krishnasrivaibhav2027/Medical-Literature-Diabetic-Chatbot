# 🏥 Medical Literature Assistant — Production-Grade Hybrid RAG

[![FastAPI](https://img.shields.io/badge/FastAPI-0.139+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)](https://react.dev/)
[![Vite](https://img.shields.io/badge/Vite-8-646CFF?logo=vite&logoColor=white)](https://vitejs.dev/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-pgvector-4169E1?logo=postgresql&logoColor=white)](https://github.com/pgvector/pgvector)
[![Upstash Redis](https://img.shields.io/badge/Upstash-Redis-00E699?logo=redis&logoColor=white)](https://upstash.com/)
[![LangChain](https://img.shields.io/badge/LangGraph-StateGraph-1C3C3C?logo=langchain&logoColor=white)](https://langchain.com/)
[![LangSmith](https://img.shields.io/badge/LangSmith-Observability-orange?logo=langchain&logoColor=white)](https://smith.langchain.com/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)](https://www.docker.com/)

An enterprise-ready, high-throughput Medical Retrieval-Augmented Generation (RAG) assistant designed for clinicians and researchers. Built with **FastAPI**, **React 19**, **PostgreSQL + pgvector (HNSW)**, **Upstash Redis**, **Jina AI Reranker v3.5**, and **LangSmith** full-stack observability.

---

## 🌟 Architecture & Key Features

```
                                      ┌────────────────────────────────────────────────────────┐
                                      │                      User Query                        │
                                      └──────────────────────────┬─────────────────────────────┘
                                                                 │
                                          ┌──────────────────────▼──────────────────────┐
                                          │     Upstash Redis Semantic & QA Cache       │
                                          └───────┬───────────────────────────────┬─────┘
                                      [Hit]       │                               │ [Miss]
                         ┌────────────────────────┘                               └─────────────────────────┐
                         ▼                                                                                  ▼
         ┌──────────────────────────────┐                                                        ┌───────────────────────┐
         │ Instant Response (0ms - 50ms)│                                                        │   Query Rewriting     │
         └──────────────────────────────┘                                                        └──────────┬────────────┘
                                                                                                            │
                                                                       ┌────────────────────────────────────┴───────────────────────────────────┐
                                                                       │                                                                        │
                                                                       ▼                                                                        ▼
                                                        ┌─────────────────────────────┐                                          ┌─────────────────────────────┐
                                                        │     Dense Vector Search     │                                          │     Sparse Keyword Search   │
                                                        │  (Gemma 300m + pgvector)    │                                          │      (Rank-BM25 Engine)     │
                                                        └──────────────┬──────────────┘                                          └──────────────┬──────────────┘
                                                                       │                                                                        │
                                                                       └────────────────────────────────────┬───────────────────────────────────┘
                                                                                                            │
                                                                                                            ▼
                                                                                             ┌─────────────────────────────┐
                                                                                             │ Reciprocal Rank Fusion(RRF) │
                                                                                             └──────────────┬──────────────┘
                                                                                                            │
                                                                                             ┌──────────────▼──────────────┐
                                                                                             │  Jina AI Reranker (v3.5)    │
                                                                                             │ (Zero-Downtime RRF Fallback)│
                                                                                             └──────────────┬──────────────┘
                                                                                                            │
                                                                                             ┌──────────────▼──────────────┐
                                                                                             │ LangGraph Multi-Node Engine │
                                                                                             │   (Tiktoken Token Tracking) │
                                                                                             └──────────────┬──────────────┘
                                                                                                            │
                                                                                             ┌──────────────▼──────────────┐
                                                                                             │ Server-Sent Events (SSE)    │
                                                                                             │ + LangSmith Tracing Cloud   │
                                                                                             └─────────────────────────────┘
```

### 1. Multi-Stage Hybrid Retrieval & Fusion
- **Dense Vector Search**: Powered by `google/embeddinggemma-300m` (768-dim) and PostgreSQL `pgvector` with HNSW indexing ($m=16, ef\_construction=64$).
- **Sparse BM25 Keyword Search**: Exact medical keyword matching (e.g., dosages, drug contraindications, specific lab codes) via Rank-BM25.
- **Reciprocal Rank Fusion (RRF, $k=60$)**: Merges dense and sparse score distributions into a calibrated unified ranking.
- **Jina AI Serverless Reranking (v3.5)**: Cross-encoder reranker deployed via external low-latency API (`https://api.jina.ai/v1/rerank`), with an automatic zero-downtime fallback to raw RRF if the reranker endpoint is unreachable.

### 2. Multi-Tier High-Performance Caching
- **Precomputed QA Cache**: Deterministic matching for standard medical inquiries with instant retrieval.
- **Semantic Similarity Cache**: Vector similarity matching on incoming queries to eliminate redundant RAG traversals.
- **Query Embedding Cache**: Prevents duplicate inference for identical query vectors.
- **Streaming Token Buffer**: Buffers SSE tokens and automatically writes to Redis on stream completion.

### 3. Production Observability with LangSmith & Tiktoken
- **Real-time Tracing**: Complete trace graphs for prompt rewriting, retrieval nodes, reranking, and generation.
- **Accurate Token Tracking**: Custom `TiktokenChatOpenAI` computes exact BPE tokens (`cl100k_base`) on both prompt and streaming completion, ensuring full token and cost visibility in LangSmith even when upstream proxies omit usage metadata chunks.

### 4. Modern Clinical UI
- **React 19 & Vite 8**: Ultra-fast hot reloading and production bundle under 500ms.
- **SSE Streaming**: Real-time token streaming with Markdown and syntax highlighting.
- **Session & Thread Management**: Multi-thread conversation history with confirmation modals for thread deletion and clear-all operations.

---

## 📊 Benchmark Results

| Metric | Baseline Architecture | Current Production Version | Improvement |
| :--- | :---: | :---: | :---: |
| **End-to-End Latency** | `40.10s` | **`16.39s`** | **59.1% Faster** |
| **Time-to-First-Token (TTFT)** | `~34.00s` | **`~6.70s`** | **80.3% Faster** |
| **Retrieval & Rerank Phase** | `24.60s` | **`1.14s`** | **95.4% Faster** |
| **P95 Semantic Cache Response** | N/A | **`42ms`** | **Instantaneous** |

*For full evaluation details, see [PRODUCTION_BENCHMARK_REPORT.md](PRODUCTION_BENCHMARK_REPORT.md).*

---

## 📁 Repository Structure

```
Hybrid_RAG/
├── backend/
│   ├── auth/                    # JWT Authentication & user verification
│   ├── chatbot/
│   │   ├── hybrid_workflow.py   # LangGraph state machine & hybrid RAG nodes
│   │   ├── service.py           # Streaming generator & SSE handler
│   │   ├── schemas.py           # Pydantic request/response schemas
│   │   ├── token_buffer.py      # Resilient stream buffer & Redis writer
│   │   └── models.py            # Chat session and thread SQLAlchemy models
│   ├── core/
│   │   ├── config.py            # Pydantic settings & LangSmith environment sync
│   │   ├── database.py          # PostgreSQL async engine & connection pool
│   │   ├── redis.py             # Upstash Redis client & cache manager
│   │   ├── semantic_cache.py    # Multi-tier semantic cache
│   │   ├── token_counter.py     # Tiktoken wrapper for LangSmith streaming tokens
│   │   └── security.py          # Password hashing (Argon2 / Bcrypt)
│   ├── ingestion_pipeline/
│   │   ├── ingestion.py         # PDF chunking, embedding & pgvector loading
│   │   └── ragas_automated_tests.py
│   ├── knowledge_base/          # Source clinical PDF documents
│   ├── prompts/                 # Modular LLM prompts (router, rewrite, summary)
│   ├── scripts/                 # Database migrations & Redis seeding scripts
│   ├── main.py                  # FastAPI application entrypoint
│   ├── requirements.txt         # Pinned backend dependencies
│   └── .env.example             # Backend environment template
├── frontend/
│   ├── src/
│   │   ├── components/          # ChatArea, Sidebar, Modals, MarkdownView
│   │   ├── services/            # API client & SSE stream reader
│   │   ├── App.jsx              # Main React application
│   │   └── index.css            # Dark mode aesthetic & design system
│   ├── package.json             # Frontend dependencies & scripts
│   ├── vite.config.js           # Vite configuration
│   └── .env.example             # Frontend environment template
├── scripts/
│   └── pgvector_binaries/       # Precompiled PostgreSQL 18 Windows extension
├── Dockerfile                   # Multi-stage production container for Cloud Run
├── .dockerignore                # Optimized Docker ignore rules
├── .gitignore                   # Comprehensive secrets & build ignores
├── install_pgvector.bat         # Windows PostgreSQL pgvector installer
├── PRODUCTION_BENCHMARK_REPORT.md
└── README.md
```

---

## 🚀 Quickstart Guide

### Prerequisites
- **Python**: 3.11+
- **Node.js**: 18+ and `npm`
- **PostgreSQL**: 15+ with `pgvector` extension enabled
- **Upstash Redis**: Serverless Redis database ([upstash.com](https://upstash.com/))
- **LLM API Key**: OpenAI or XKiro proxy API key
- **Jina AI API Key**: Free/paid key from [jina.ai](https://jina.ai/)

---

### Step 1: Clone the Repository

```bash
git clone https://github.com/<your-username>/Hybrid_RAG.git
cd Hybrid_RAG
```

---

### Step 2: Backend Setup

1. **Create and activate a virtual environment**:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Install dependencies**:
   ```bash
   pip install --upgrade pip
   pip install -r backend/requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp backend/.env.example backend/.env
   ```
   Open `backend/.env` and supply your credentials:
   - `DATABASE_URL`: `postgresql+asyncpg://<user>:<password>@localhost:5432/HybridRAG`
   - `SECRET_KEY`: A secure random string for JWT auth
   - `XKIRO_API_KEY` (or OpenAI API Key)
   - `UPSTASH_REDIS_REST_URL` & `UPSTASH_REDIS_REST_TOKEN`
   - `JINA_API_KEY`
   - `LANGCHAIN_API_KEY` & `LANGCHAIN_PROJECT` *(optional for tracing)*

4. **Initialize PostgreSQL pgvector**:
   Ensure PostgreSQL is running and create the extension:
   ```sql
   CREATE DATABASE "HybridRAG";
   \c "HybridRAG"
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   *(On Windows, run `install_pgvector.bat` as Administrator if using the included local binaries).*

5. **Run Database Migrations & Ingestion**:
   ```bash
   # Ingest knowledge base PDFs into pgvector
   python -m backend.ingestion_pipeline.ingestion

   # Optional: Seed precomputed Redis QA cache
   python -m backend.scripts.seed_precomputed_qa
   ```

6. **Start the FastAPI backend**:
   ```bash
   uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```
   The backend API will be live at `http://localhost:8000` (Interactive docs: `http://localhost:8000/docs`).

---

### Step 3: Frontend Setup

1. **Navigate to the frontend directory**:
   ```bash
   cd frontend
   ```

2. **Install npm dependencies**:
   ```bash
   npm install
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Verify `VITE_API_URL=http://localhost:8000`.

4. **Launch the development server**:
   ```bash
   npm run dev
   ```
   Open your browser at `http://localhost:5173`.

---

## 🐳 Docker Deployment

The provided `Dockerfile` is optimized for production container platforms such as **Google Cloud Run**, **AWS ECS**, or **Kubernetes**. It pre-downloads the `google/embeddinggemma-300m` model weights during the image build step, eliminating a 600MB download during container startup.

### Build and Run Locally:

```bash
# Build the container image
docker build -t hybrid-rag-backend:latest .

# Run container binding to port 8080
docker run -p 8080:8080 --env-file backend/.env hybrid-rag-backend:latest
```

---

## ☁️ Cloud Deployment Guide

### Backend: Google Cloud Run
1. Set up a serverless PostgreSQL instance (e.g., **Supabase**, **Neon**, or **Cloud SQL with pgvector**).
2. Build and submit image to Google Artifact Registry:
   ```bash
   gcloud builds submit --tag gcr.io/<PROJECT_ID>/hybrid-rag-backend
   ```
3. Deploy to Cloud Run:
   ```bash
   gcloud run deploy hybrid-rag-backend \
     --image gcr.io/<PROJECT_ID>/hybrid-rag-backend \
     --platform managed \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars DATABASE_URL="postgresql+asyncpg://...",UPSTASH_REDIS_REST_URL="...",UPSTASH_REDIS_REST_TOKEN="..."
   ```

### Frontend: Vercel / Cloudflare Pages
1. Import the repository in [Vercel](https://vercel.com).
2. Set **Root Directory** to `frontend`.
3. Set **Build Command** to `npm run build`.
4. Set **Output Directory** to `dist`.
5. Add Environment Variable:
   - `VITE_API_URL`: `https://<YOUR-CLOUD-RUN-URL>.a.run.app`

---

## 🔒 Security & Best Practices

- **Never commit `.env` files**: All secrets and credentials are excluded via root `.gitignore`.
- **Non-root Docker Execution**: Container runs under a dedicated `appuser` (UID 1000).
- **JWT Authentication**: User endpoints require Bearer JWT authorization with configurable token lifetimes.
- **Fail-safe Reranker**: Automatic circuit breaking ensures zero clinical workflow disruptions if the external reranker API is degraded.

---

## 📄 License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.
