import sys
import asyncio

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from contextlib import asynccontextmanager
from fastapi import FastAPI
from backend.core.config import settings
from backend.core.database import engine, Base, ensure_database_exists
from backend.core.logging import logger

import os
if (settings.LANGCHAIN_TRACING_V2 or os.getenv("LANGSMITH_TRACING") == "true") and settings.LANGCHAIN_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGCHAIN_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGSMITH_API_KEY"] = settings.LANGCHAIN_API_KEY
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGCHAIN_PROJECT
    os.environ["LANGSMITH_PROJECT"] = settings.LANGCHAIN_PROJECT
    os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    os.environ["LANGSMITH_ENDPOINT"] = settings.LANGCHAIN_ENDPOINT
    logger.info("LangSmith tracing enabled for project: '%s'", settings.LANGCHAIN_PROJECT)
from backend.middleware.cors import apply_cors_middleware
from backend.middleware.timing import RequestTimingMiddleware
from backend.middleware.logging import LoggingMiddleware
from backend.middleware.exception import ExceptionMiddleware
from backend.auth.router import router as auth_router
from backend.users.router import router as users_router
from backend.chatbot.router import router as chatbot_router
from backend.chatbot.hybrid_workflow import get_embedding_model, get_chat_app
from backend.core.redis import cache_manager

async def prewarm_models():
    """
    Cold-Start Model Weight Pre-Warming Hook.
    Pre-loads google/embeddinggemma-300m and CrossEncoder reranker weights into CPU RAM,
    and encodes a dummy token at startup so user queries never encounter cold-start latency.
    """
    import time
    start_t = time.perf_counter()
    logger.info("Starting model weight pre-warming hook...")

    # 1. Warm up SentenceTransformer ('google/embeddinggemma-300m')
    model = get_embedding_model()
    # Execute dummy inference in a separate thread so the async event loop is never blocked
    await asyncio.to_thread(model.encode, "dummy warmup query token", show_progress_bar=False)
    logger.info("SentenceTransformer('google/embeddinggemma-300m') pre-warmed with dummy token.")

    # 2. Pre-warm BM25 sparse index from PostgreSQL into in-memory cache
    try:
        from backend.chatbot.bm25 import get_bm25_index
        await get_bm25_index()
        logger.info("BM25 in-memory index pre-warmed from document_chunks.")
    except Exception as e:
        logger.warning("BM25 pre-warmup warning (non-fatal): %s", e)

    elapsed_ms = int((time.perf_counter() - start_t) * 1000)
    logger.info("Cold-start model pre-warming completed in %d ms.", elapsed_ms)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Database existence check and table schema initialization
    logger.info("Setting up database tables...")
    await ensure_database_exists()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 2. Cold-start model weight pre-warming hook
    await prewarm_models()

    # 3. LangGraph checkpointer & workflow compilation
    logger.info("Initializing chat workflow checkpointer...")
    await get_chat_app()

    # 4. Redis cache connection verification
    logger.info("Verifying Upstash Redis connection...")
    redis_ok = await cache_manager.ping()
    if redis_ok:
        logger.info("Upstash Redis connected successfully.")
    else:
        logger.warning("Upstash Redis connection could not be established; running with graceful degradation.")

    # 5. Pre-computed Semantic Q&A Cache initialization (happens once, skipped if already populated)
    logger.info("Initializing Pre-computed Semantic Q&A Cache...")
    from backend.core.database import AsyncSessionLocal
    from backend.core.semantic_cache import semantic_cache_manager
    async with AsyncSessionLocal() as session:
        await semantic_cache_manager.seed_if_empty(session)
        await semantic_cache_manager.load_index(session)
    logger.info("Pre-computed Semantic Q&A Cache ready.")

    logger.info("Backend services ready to receive requests.")

    yield

    logger.info("Application shutting down...")

app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG
)

apply_cors_middleware(app)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(LoggingMiddleware)
app.add_middleware(ExceptionMiddleware)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(chatbot_router)

@app.get("/")
async def root():
    return {
        "message":"Welcome to your Diabetic medical literature assistant"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
