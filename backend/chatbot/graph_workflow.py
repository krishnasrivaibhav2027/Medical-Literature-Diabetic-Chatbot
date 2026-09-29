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
from typing import TypedDict, Annotated, Sequence, List
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, BaseMessage, AIMessage
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI
from backend.core.config import settings
from backend.chatbot.schemas import QueryIntent
from backend.prompts.router import ROUTER_PROMPT
from backend.prompts.conversation import CONVERSATION_PROMPT
from backend.chatbot.bm25 import retreive_using_bm25
from backend.chatbot.reranker import reranker
from backend.chatbot.rrf import rrf_score

warnings.filterwarnings("ignore", message="Pydantic serializer warnings", category=UserWarning)

logger = logging.getLogger("app.workflow")


model = ChatOpenAI(
  model="openai/gpt-oss-20b",
  base_url = "https://integrate.api.nvidia.com/v1",
  api_key = settings.NVIDIA_API_KEY,
  temperature=0.2,
)

embedding_model = SentenceTransformer("google/embeddinggemma-300m")


class ChatState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    query: str
    retrieved_docs: str
    retrieved_metadata: List[dict]
    response: str
    intent: str

async def router_node(state: ChatState):
    query = state.get("query") or (state["messages"][-1].content if state.get("messages",[]) else "")
    router_chain = ROUTER_PROMPT | model.with_structured_output(QueryIntent)
    intent_obj = await router_chain.ainvoke({"query":query})
    return {"intent": intent_obj.intent}

def route_after_query_intent(state: ChatState):
    intent = state.get("intent", "")
    if intent == "Diabetes":
        return "diabetes"
    else:
        return "non_diabetes"

async def non_diabetes_node(state: ChatState):
    res = "I am only designed to answer medical questions, specifically about diabetes. Try again asking relevant questions."
    return {
        "messages": [AIMessage(content=res)],
        "response": res,
    }
    
async def retrieval_node(state: ChatState):
    query = state.get("query") or (state["messages"][-1].content if state.get("messages",[]) else "")
    query_embedding = embedding_model.encode(query).tolist()
    async with AsyncSessionLocal() as session:
        stmt = (
            select(
                DocumentChunk.content,
                DocumentChunk.metadata_json,
            )
            .order_by(DocumentChunk.embedding.cosine_distance(query_embedding))
            .limit(10)
        )
        res = await session.execute(stmt)
        rows = res.fetchall()

    retrieved_docs = "\n\n".join([row[0] for row in rows])
    retrieved_metadata = [row[1] or {} for row in rows]
    return {
        "retrieved_docs": retrieved_docs,
        "retrieved_metadata": retrieved_metadata,
    }
    
    

async def diabetes_node(state: ChatState):
    messages = state.get("messages",[])
    query = state.get("query") or (messages[-1].content if messages else "")

    if query and (not messages or messages[-1].content != query):
        messages.append(HumanMessage(content=query))

    retrieved_docs = state.get("retrieved_docs") or ""
    retrieved_metadata = state.get("retrieved_metadata") or []

    chain = CONVERSATION_PROMPT | model | StrOutputParser()

    last_err = None
    for attempt in range(5):
        try:
            if attempt > 0:
                await _asyncio.sleep(min(2 ** attempt, 8))
            
            res = await chain.ainvoke({"query": query, "messages": messages,
                "retrieved_docs": retrieved_docs,
                "retrieved_metadata": retrieved_metadata if retrieved_metadata else "None"})
            return {
                "messages": [AIMessage(content = res)],
                "response" : res
            }
        except Exception as e:
            last_err = e
            logger.warning("conversation_node attempt %d failed: %s", attempt + 1, e)
    raise RuntimeError(f"Conversation model failed after 5 attempts: {last_err}") from last_err


workflow = StateGraph(ChatState)

workflow.add_node("router", router_node)
workflow.add_node("non_diabetes_node",non_diabetes_node)
workflow.add_node("retrieval_node",retrieval_node)
workflow.add_node("diabetes_node",diabetes_node)

workflow.add_edge(START, "router")
workflow.add_conditional_edges(
    "router",
    route_after_query_intent,
    {
        "non_diabetes": "non_diabetes_node",
        "diabetes": "retrieval_node",
    }
)
workflow.add_edge("non_diabetes_node", END)
workflow.add_edge("retrieval_node", "diabetes_node")
workflow.add_edge("diabetes_node", END)

_chat_app = None
async def get_chat_app():
    global _chat_app
    if _chat_app is not None:
        return _chat_app

    conn_string = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    async with await psycopg.AsyncConnection.connect(conn_string,autocommit=True) as setup_conn:
        setup_checkpointer = AsyncPostgresSaver(setup_conn)
        await setup_checkpointer.setup()
    
    pool = AsyncConnectionPool(conninfo = conn_string, max_size=10, open=False)
    await pool.open()
    checkpointer = AsyncPostgresSaver(pool)

    _chat_app = workflow.compile(checkpointer=checkpointer)
    return _chat_app
    

