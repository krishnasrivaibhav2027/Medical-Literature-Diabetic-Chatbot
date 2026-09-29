import psycopg
import logging
import asyncio as _asyncio
from psycopg_pool import AsyncConnectionPool
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sqlalchemy import select
from backend.core.database import AsyncSessionLocal
from backend.chatbot.models import DocumentChunk
import warnings
from typing import TypedDict, Annotated, Sequence, List, Optional
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from backend.core.token_counter import TiktokenChatOpenAI, count_tokens
from backend.core.config import settings
from backend.chatbot.schemas import QueryIntent
from backend.prompts.router import ROUTER_PROMPT
from backend.prompts.conversation import CONVERSATION_PROMPT
from backend.prompts.summary import SUMMARY_PROMPT
from backend.prompts.query_rewrite import REWRITE_PROMPT
from backend.chatbot.bm25 import retrieve_using_bm25
from backend.chatbot.reranker import reranker
from backend.chatbot.rrf import rrf_score
from backend.core.redis import cache_manager, normalize_query_key

warnings.filterwarnings("ignore", message="Pydantic serializer warnings", category=UserWarning)

logger = logging.getLogger("app.workflow")


PRIMARY_MODEL = TiktokenChatOpenAI(
  model="cohere/command-a-reasoning",
  base_url = "https://api.xkiro.com/v1",
  api_key = settings.XKIRO_API_KEY,
  temperature=0.2,
)

FALL_BACK_MODELS = [
    TiktokenChatOpenAI(
        model="mistralai/mistral-medium-3.5",
        base_url="https://api.xkiro.com/v1",
        api_key=settings.XKIRO_API_KEY,
        temperature=0.2,
    ),
    TiktokenChatOpenAI(
        model="qwen/qwen3.7-flash:free",
        base_url="https://api.xkiro.com/v1",
        api_key=settings.XKIRO_API_KEY,
        temperature=0.2,
    ),
]

model = PRIMARY_MODEL.with_fallbacks(FALL_BACK_MODELS)

_embedding_model: Optional[SentenceTransformer] = None

def get_embedding_model() -> SentenceTransformer:
    """Lazy-load and return the cached SentenceTransformer singleton."""
    global _embedding_model
    if _embedding_model is None:
        logger.info("Initializing SentenceTransformer('google/embeddinggemma-300m')...")
        _embedding_model = SentenceTransformer("google/embeddinggemma-300m")
    return _embedding_model

def __getattr__(name: str):
    """Fallback for backwards-compatible access to embedding_model."""
    if name == "embedding_model":
        return get_embedding_model()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query: str
    search_query: Optional[str]
    retrieved_docs: str
    retrieved_metadata: List[dict]
    sources: List[dict]
    response: str
    intent: str
    temperature: Optional[float]
    top_p: Optional[float]
    top_k: Optional[int]
    max_tokens: Optional[int]
    reranker_top_n: Optional[int]
    summary: Optional[str]
    custom_api_key: Optional[str]
    custom_base_url: Optional[str]
    custom_model: Optional[str]
    custom_jina_api_key: Optional[str]

def resolve_llm_model(state: ChatState):
    """
    Returns custom BYOK model if user configured API keys, otherwise system default model with fallbacks.
    """
    custom_api_key = state.get("custom_api_key")
    if custom_api_key and isinstance(custom_api_key, str) and custom_api_key.strip():
        custom_base_url = state.get("custom_base_url") or "https://api.openai.com/v1"
        custom_model = state.get("custom_model") or "gpt-4o-mini"
        return TiktokenChatOpenAI(
            model=custom_model,
            base_url=custom_base_url,
            api_key=custom_api_key.strip(),
            temperature=0.2,
        )
    return model

def format_chat_history(messages: Sequence[BaseMessage], max_turns: int = 6) -> str:
    """Format recent conversation turns into a clean readable string for prompt context."""
    if not messages:
        return "No prior conversation."

    recent = messages[-max_turns:]
    history_lines = []
    for msg in recent:
        if isinstance(msg, HumanMessage):
            history_lines.append(f"User: {msg.content}")
        elif isinstance(msg, AIMessage):
            content = msg.content[:300].rsplit(" ", 1)[0] + "..." if len(msg.content) > 300 else msg.content
            history_lines.append(f"Assistant: {content}")
        elif hasattr(msg, "content"):
            history_lines.append(f"{getattr(msg, 'type', 'Message')}: {msg.content}")

    return "\n".join(history_lines) if history_lines else "No prior conversation."


async def router_node(state: ChatState):
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")
    prior_user_msgs = [m for m in messages[:-1] if isinstance(m, HumanMessage)]

    # Fast-path: Check Redis intent cache only for standalone queries without prior context
    intent_cache_key = normalize_query_key(query, prefix="rag:intent")
    if not prior_user_msgs:
        cached_intent = await cache_manager.get_str(intent_cache_key)
        if cached_intent in ("Diabetes", "Other"):
            logger.info("Router cache hit: '%s' -> %s", query[:40], cached_intent)
            return {"intent": cached_intent}

    chat_history = format_chat_history(messages[:-1], max_turns=6)

    try:
        active_model = resolve_llm_model(state)
        router_chain = ROUTER_PROMPT | active_model.with_structured_output(QueryIntent)
        intent_obj = await router_chain.ainvoke({"query": query, "chat_history": chat_history})
        classified_intent = intent_obj.intent
    except Exception as e:
        logger.warning("Router model structured output error: %s; falling back to default", e)
        classified_intent = "Diabetes" if prior_user_msgs else "Other"

    # Store intent in Redis ONLY for standalone queries (TTL: 7 days = 604,800s)
    if not prior_user_msgs:
        await cache_manager.set_str(intent_cache_key, classified_intent, expire_seconds=604800)

    return {"intent": classified_intent}

SUMMARY_INTERVAL_TURNS = 10

def should_summarize(state: ChatState) -> bool:
    """Trigger summarization every SUMMARY_INTERVAL_TURNS user conversations in this thread."""
    messages = state.get("messages", [])
    user_turns = sum(1 for m in messages if isinstance(m, HumanMessage))
    return user_turns > 0 and user_turns % SUMMARY_INTERVAL_TURNS == 0

def route_after_query_intent(state: ChatState):
    intent = state.get("intent", "")
    if intent != "Diabetes":
        return "non_diabetes"
    
    if should_summarize(state):
        return "summarizer"
    
    return "retrieval"

async def non_diabetes_node(state: ChatState):
    res = "I am only designed to answer medical questions, specifically about diabetes. Try again asking relevant questions."
    out_tok = count_tokens(res)
    usage_meta = {"input_tokens": 5, "output_tokens": out_tok, "total_tokens": 5 + out_tok}
    return {
        "messages": [AIMessage(content=res, usage_metadata=usage_meta)],
        "response": res,
    }

async def summarizer_node(state: ChatState):
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")
    previous_summary = state.get("summary") or "None (initial summary)."
    
    conversation_history = "\n".join(
        f"{'Patient' if isinstance(m, HumanMessage) else 'Assistant'}: {m.content}"
        for m in messages[:-1]
    )
    if not conversation_history:
        conversation_history = "Initial dialogue interval."
    
    active_model = resolve_llm_model(state)
    chain = SUMMARY_PROMPT | active_model | StrOutputParser()
    try:
        new_summary = await chain.ainvoke({
            "previous_summary": previous_summary,
            "query": query,
            "conversation_history": conversation_history,
        })
    except Exception as e:
        logger.warning("Summarizer node error: %s", e)
        new_summary = state.get("summary") or "Prior conversation summary unavailable."
        
    return {"summary": new_summary}

async def query_rewriter_node(state: ChatState):
    """
    Conversational Query Reformulation Node:
    Rewrites follow-up queries with anaphoric pronouns or formatting requests into a
    standalone, fully-specified clinical search query using recent chat context.
    """
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")

    prior_messages = messages[:-1] if len(messages) > 1 else []
    if not prior_messages:
        return {"search_query": query}

    chat_history = format_chat_history(prior_messages, max_turns=6)
    if chat_history == "No prior conversation.":
        return {"search_query": query}

    try:
        active_model = resolve_llm_model(state)
        rewrite_chain = REWRITE_PROMPT | active_model | StrOutputParser()
        rewritten = await rewrite_chain.ainvoke({
            "query": query,
            "chat_history": chat_history,
        })
        rewritten_clean = rewritten.strip().strip('"').strip("'").strip()
        if rewritten_clean and len(rewritten_clean) > 3 and "\n" not in rewritten_clean:
            logger.info("Query rewritten for retrieval: '%s' -> '%s'", query[:40], rewritten_clean[:60])
            return {"search_query": rewritten_clean}
    except Exception as e:
        logger.warning("Query rewriter error: %s; using original query", e)

    return {"search_query": query}


async def retrieval_node(state: ChatState):
    """
    Hybrid Retrieval Pipeline:
    1. Vector Search (Dense) across PostgreSQL pgvector store.
    2. BM25 Search (Sparse) across all indexed documents.
    3. Reciprocal Rank Fusion (RRF) to merge candidate lists.
    4. Cross-Encoder Reranker to select the top most relevant chunks.
    5. Returns both formatted document texts and aligned metadatas.
    """
    search_query = state.get("search_query") or state.get("query") or (state["messages"][-1].content if state.get("messages", []) else "")
    query = search_query
    
    # 0. Pre-computed Semantic Cache Check (Bypasses heavy dense/sparse/reranker if precomputed FAQ matches)
    try:
        from backend.core.semantic_cache import semantic_cache_manager
        sem_match = await semantic_cache_manager.find_match(query)
        if sem_match:
            logger.info("Retrieval node pre-computed semantic cache hit for query: '%s'", query[:40])
            return {
                "retrieved_docs": sem_match["answer"],
                "retrieved_metadata": [{
                    "source": "Precomputed Clinical Guideline Cache",
                    "title": sem_match["canonical_question"],
                    "category": sem_match.get("category", "Diabetes"),
                }],
                "sources": sem_match.get("sources", []),
            }
    except Exception as e:
        logger.warning("Error checking semantic cache in retrieval_node: %s", e)

    # 1. Dense Vector Search (with Redis embedding cache)
    embed_cache_key = normalize_query_key(query, prefix="rag:embed")
    query_embedding = await cache_manager.get_json(embed_cache_key)
    if not query_embedding or not isinstance(query_embedding, list):
        model_obj = get_embedding_model()
        query_embedding = model_obj.encode(query).tolist()
        await cache_manager.set_json(embed_cache_key, query_embedding, expire_seconds=1209600)  # 14 days
    else:
        logger.info("Embedding cache hit for query: '%s'", query[:40])

    # 1 & 2. Parallel Dense Vector Search (pgvector) and Sparse Search (BM25)
    async def _dense_search() -> List[dict]:
        async with AsyncSessionLocal() as session:
            stmt = (
                select(
                    DocumentChunk.id,
                    DocumentChunk.content,
                    DocumentChunk.metadata_json,
                    DocumentChunk.embedding.cosine_distance(query_embedding).label("distance"),
                )
                .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
                .limit(25)
            )
            res = await session.execute(stmt)
            rows = res.fetchall()

        return [
            {
                "id": row.id,
                "text": row.content,
                "metadata": row.metadata_json or {},
                "distance": float(row.distance) if row.distance is not None else 0.0,
            }
            for row in rows
        ]

    vector_docs, bm25_docs = await _asyncio.gather(
        _dense_search(),
        retrieve_using_bm25(query, top_k=25),
    )

    # 3. Reciprocal Rank Fusion (RRF)
    top_n_setting = state.get("reranker_top_n")
    if top_n_setting is not None and isinstance(top_n_setting, (int, float)) and top_n_setting >= 1:
        top_n = int(top_n_setting)
    else:
        top_n = 10

    candidate_k = min(50, max(top_n * 2, 20))
    fused_docs = await rrf_score([vector_docs, bm25_docs], k=60, top_k=candidate_k)

    # 4. Jina Serverless Reranker API (supports optional BYOK Jina key)
    reranked_docs = await reranker(
        query,
        fused_docs,
        top_n=top_n,
        api_key=state.get("custom_jina_api_key"),
    )

    retrieved_docs = "\n\n".join([doc["text"] for doc in reranked_docs])
    retrieved_metadata = [doc["metadata"] for doc in reranked_docs]

    import math
    sources = []
    for doc in reranked_docs[:top_n]:
        meta = doc.get("metadata", {})
        raw_source = meta.get("source", "Clinical Knowledge Base")
        title = meta.get("title") or raw_source.replace(".pdf", "").replace("_", " ").replace("-", " ").strip()
        page = meta.get("page")
        section = f"Page {page}" if page is not None else "Clinical Reference Chunk"

        raw_score = doc.get("rerank_score", 0.0)
        try:
            norm_score = 1.0 / (1.0 + math.exp(-raw_score))
        except OverflowError:
            norm_score = 1.0 if raw_score > 0 else 0.0

        raw_snippet = doc.get("text", "")
        clean_snippet = raw_snippet.strip()
        if len(clean_snippet) > 300:
            clean_snippet = clean_snippet[:300].rsplit(" ", 1)[0] + "..."

        sources.append({
            "id": doc.get("id"),
            "title": title or raw_source,
            "section": section,
            "score": round(norm_score, 3),
            "retrieval_method": "pgvector Dense + BM25 + Jina Reranker",
            "content": clean_snippet,
            "url": meta.get("url", ""),
        })

    return {
        "retrieved_docs": retrieved_docs,
        "retrieved_metadata": retrieved_metadata,
        "sources": sources,
    }
    

async def diabetes_node(state: ChatState):
    messages = state.get("messages", [])
    query = state.get("query") or (messages[-1].content if messages else "")

    if query and (not messages or messages[-1].content != query):
        messages.append(HumanMessage(content=query))

    retrieved_docs = state.get("retrieved_docs") or ""
    retrieved_metadata = state.get("retrieved_metadata") or []

    # Dynamically bind sampling/generation parameters from settings
    bind_kwargs = {}
    if state.get("temperature") is not None:
        bind_kwargs["temperature"] = float(state["temperature"])
    if state.get("top_p") is not None:
        bind_kwargs["top_p"] = float(state["top_p"])
    if state.get("max_tokens") is not None:
        bind_kwargs["max_tokens"] = int(state["max_tokens"])
    if state.get("top_k") is not None:
        bind_kwargs["extra_body"] = {"top_k": int(state["top_k"])}

    base_model = resolve_llm_model(state)
    active_model = base_model.bind(**bind_kwargs) if bind_kwargs else base_model
    chain = CONVERSATION_PROMPT | active_model | StrOutputParser()

    last_err = None
    for attempt in range(5):
        try:
            if attempt > 0:
                await _asyncio.sleep(min(2 ** attempt, 8))
            
            res = await chain.ainvoke({
                "query": query,
                "messages": messages[:-1] if messages and messages[-1].content == query else messages,
                "summary": state.get("summary") or "No prior summary available.",
                "retrieved_docs": retrieved_docs,
                "retrieved_metadata": retrieved_metadata if retrieved_metadata else "None",
            })
            in_tok = count_tokens(query) + count_tokens(retrieved_docs)
            out_tok = count_tokens(res)
            usage_meta = {
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "total_tokens": in_tok + out_tok,
            }
            return {
                "messages": [AIMessage(content=res, usage_metadata=usage_meta)],
                "response": res,
            }
        except Exception as e:
            last_err = e
            logger.warning("conversation_node attempt %d failed: %s", attempt + 1, e)
    raise RuntimeError(f"Conversation model failed after 5 attempts: {last_err}") from last_err


workflow = StateGraph(ChatState)

workflow.add_node("router", router_node)
workflow.add_node("non_diabetes_node", non_diabetes_node)
workflow.add_node("summarizer_node", summarizer_node)
workflow.add_node("query_rewriter_node", query_rewriter_node)
workflow.add_node("retrieval_node", retrieval_node)
workflow.add_node("diabetes_node", diabetes_node)

workflow.add_edge(START, "router")
workflow.add_conditional_edges(
    "router",
    route_after_query_intent,
    {
        "non_diabetes": "non_diabetes_node",
        "summarizer": "summarizer_node",
        "retrieval": "query_rewriter_node",
    }
)
workflow.add_edge("non_diabetes_node", END)
workflow.add_edge("summarizer_node", "query_rewriter_node")
workflow.add_edge("query_rewriter_node", "retrieval_node")
workflow.add_edge("retrieval_node", "diabetes_node")
workflow.add_edge("diabetes_node", END)

_chat_app = None
async def get_chat_app():
    global _chat_app
    if _chat_app is not None:
        return _chat_app

    conn_string = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    # psycopg expects 'sslmode' instead of 'ssl' (which asyncpg uses)
    conn_string = conn_string.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

    async with await psycopg.AsyncConnection.connect(conn_string, autocommit=True) as setup_conn:
        setup_checkpointer = AsyncPostgresSaver(setup_conn)
        await setup_checkpointer.setup()
    
    pool = AsyncConnectionPool(conninfo=conn_string, max_size=10, open=False)
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)

    _chat_app = workflow.compile(checkpointer=checkpointer)
    return _chat_app
