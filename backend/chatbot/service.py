import uuid
import time
import asyncio
import logging
from datetime import datetime, UTC
from typing import List, Optional, Dict, Any, AsyncGenerator
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from backend.users.models import User
from backend.chatbot.models import ChatThread, ChatMessage, PrecomputedQA
from backend.core.database import get_db
from backend.chatbot.hybrid_workflow import get_chat_app, model as active_llm_model
from backend.chatbot.schemas import (
    MessageSchema,
    ChatResponse,
    StreamTokenData,
    StreamMetadata,
    StreamErrorData,
    StreamEvent,
)
from langchain_core.messages import HumanMessage, AIMessage, RemoveMessage, BaseMessage
from backend.core.redis import cache_manager, normalize_query_key
from backend.core.semantic_cache import semantic_cache_manager
from backend.core.config import settings
from backend.chatbot.token_buffer import token_buffer_manager, tokenize_into_stream_tokens
from backend.core.token_counter import count_tokens
from langchain_core.output_parsers import StrOutputParser

logger = logging.getLogger(__name__)


async def _watch_disconnect(request: Request, task: asyncio.Task, poll_interval: float = 0.5) -> None:
    """Cancel *task* if the SSE client disconnects."""
    try:
        while not task.done():
            if await request.is_disconnected():
                logger.info("Client disconnected, cancelling task")
                task.cancel()
                return
            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        pass

def _extract_text(raw) -> str:
    """Extract plain text from an AIMessage content (str or list of content parts)."""
    if isinstance(raw, list):
        return "".join(
            p.get("text", "") for p in raw
            if isinstance(p, dict)
            and not p.get("thought")
            and p.get("type") not in ("thought", "thinking")
        )
    return raw if isinstance(raw, str) else str(raw)


def format_llm_error_message(e: Exception) -> str:
    """
    Format upstream LLM exceptions into clear, actionable advice for the user.
    """
    err_str = str(e)
    err_lower = err_str.lower()

    # 1. Model Not Found (404)
    if (
        "404" in err_str
        or "not_found" in err_lower
        or "does not exist" in err_lower
        or "model_not_found" in err_lower
    ):
        return (
            "The configured AI model was not found by the API provider (404 Not Found). "
            "This usually happens when an invalid model name is specified or the provider has retired it. "
            "Please switch to another AI model (e.g., OpenAI GPT-4o, Groq Llama 3.3, or Cohere Command A) in Model Settings."
        )

    # 2. Authentication / API Key issues (401 / 403)
    if (
        "401" in err_str
        or "403" in err_str
        or "invalid_api_key" in err_lower
        or "incorrect api key" in err_lower
        or "unauthorized" in err_lower
        or "authentication" in err_lower
    ):
        return (
            "The AI model provider rejected the request due to an invalid or missing API key (401/403 Unauthorized). "
            "Please verify your API key in Model Settings or switch to a different AI service or system default."
        )

    # 3. Rate Limit / Quota Exceeded (429)
    if (
        "429" in err_str
        or "rate_limit" in err_lower
        or "quota" in err_lower
        or "too many requests" in err_lower
        or "insufficient_quota" in err_lower
    ):
        return (
            "The AI provider's rate limit or usage quota was exceeded (429 Too Many Requests). "
            "Please switch to a different AI model provider (such as Groq Cloud or OpenAI) in Model Settings, or try again in a few moments."
        )

    # 4. Service Unavailable / Provider Outage (500 / 502 / 503 / 504)
    if any(code in err_str for code in ["500", "502", "503", "504"]) or any(k in err_lower for k in ["overloaded", "bad gateway", "service unavailable", "internalservererror"]):
        return (
            "The AI provider is temporarily unavailable or experiencing high traffic (5xx Server Error). "
            "Please switch to an alternative AI model or provider in Model Settings, or try again in a moment."
        )

    # 5. Connection / Timeout
    if any(k in err_lower for k in ["timeout", "timed out", "connection", "connecterror"]):
        return (
            "Network timeout connecting to the AI provider. "
            "Please check your internet connection or switch to another AI provider in Model Settings."
        )

    # 6. Fallback with cleaned error detail
    clean_msg = err_str
    if "Conversation model failed after 5 attempts:" in clean_msg:
        clean_msg = clean_msg.split("Conversation model failed after 5 attempts:")[-1].strip()
    if len(clean_msg) > 200:
        clean_msg = clean_msg[:200] + "..."

    return (
        f"The AI model provider encountered an issue: {clean_msg}. "
        "Please select a different AI model or API service in Model Settings."
    )


_llm_semaphore: Optional[asyncio.Semaphore] = None


def get_llm_semaphore() -> asyncio.Semaphore:
    """Return a shared singleton Semaphore to limit concurrent LLM workflow executions."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(10)
    return _llm_semaphore


class ChatbotService:
    def __init__(self, db: AsyncSession = Depends(get_db)):
        self.db = db


    async def _save_message(
        self, session_id: str, role: str, content: str, user_id: int, user_query: Optional[str] = None
    ) -> None:
        try:
            res = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread = res.scalar_one_or_none()
            preview_text = (user_query or (content if role == "user" else None))
            if preview_text:
                preview_text = preview_text.strip()[:100]

            if not thread:
                thread = ChatThread(
                    thread_id=session_id,
                    preview=preview_text or "New Conversation",
                    updated_at=datetime.now(UTC).replace(tzinfo=None),
                    user_id=user_id,
                )
                self.db.add(thread)
                await self.db.flush()
            else:
                # Update preview if thread currently has the default "New Conversation" or is empty
                if preview_text and (not thread.preview or thread.preview == "New Conversation"):
                    thread.preview = preview_text

            self.db.add(ChatMessage(thread_id=thread.id, role=role, content=content))
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to save message [thread=%s role=%s]: %s", session_id, role, e, exc_info=True)

    async def _update_thread_metadata(self, session_id: str, intent: str, user_query: Optional[str] = None) -> None:
        try:
            res = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread = res.scalar_one_or_none()
            if thread:
                thread.intent = intent
                if user_query and (not thread.preview or thread.preview == "New Conversation"):
                    thread.preview = user_query.strip()[:100]
                thread.updated_at = datetime.now(UTC).replace(tzinfo=None)
                await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to update thread metadata [thread=%s]: %s", session_id, e, exc_info=True)

    async def _get_thread_langchain_messages(self, session_id: str, limit: int = 12) -> List[BaseMessage]:
        """
        Retrieves recent conversation history from ChatMessage for this session_id,
        converted to LangChain BaseMessage objects with stable database IDs.
        """
        try:
            thread_res = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread = thread_res.scalar_one_or_none()
            if not thread:
                return []

            msg_res = await self.db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == thread.id)
                .order_by(ChatMessage.id.desc())
                .limit(limit)
            )
            raw_messages = list(reversed(msg_res.scalars().all()))

            lc_messages: List[BaseMessage] = []
            for m in raw_messages:
                if (
                    m.role == "user"
                    and lc_messages
                    and isinstance(lc_messages[-1], HumanMessage)
                    and lc_messages[-1].content.strip() == m.content.strip()
                ):
                    continue
                if m.role == "user":
                    lc_messages.append(HumanMessage(content=m.content, id=f"db_{m.id}"))
                elif m.role == "assistant":
                    lc_messages.append(AIMessage(content=m.content, id=f"db_{m.id}"))

            return lc_messages
        except Exception as e:
            logger.error("Failed to retrieve thread langchain messages for thread=%s: %s", session_id, e, exc_info=True)
            return []

    # ── main streaming endpoint ──────────────────────────────────────────

    async def chat_stream(
        self,
        user_message: str,
        user: User,
        thread_id: str,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        reranker_top_n: Optional[int] = None,
        request: Optional[Request] = None,
        is_regenerate: bool = False,
        stream_mode: Optional[str] = "burst",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        SSE events:
            token     — text chunk from the LLM
            metadata  — final stats (thread_id, tokens, timing, intent)
            error     — something went wrong
        """
        user_id = user.id
        session_id = thread_id or str(uuid.uuid4())
        active_thread_id = f"user_{user_id}_{session_id}"
        start_time = time.perf_counter()
        logger.info("chat_stream | session=%s temp=%s top_p=%s top_k=%s top_n=%s is_regen=%s", session_id, temperature, top_p, top_k, reranker_top_n, is_regenerate)

        # Strict Enforcement: AI Model API key is mandatory to access the chatbot
        custom_api_key = (request.headers.get("x-llm-api-key") or "").strip() if request else ""
        if not custom_api_key:
            logger.warning("Rejecting chat stream: Missing mandatory LLM API key | session=%s", session_id)
            yield StreamEvent(
                event="error",
                data=StreamErrorData(
                    message="An AI Model API Key is mandatory to use the chatbot. Please open Model Settings and enter your API key to activate access."
                ).model_dump(),
            ).model_dump()
            return

        if is_regenerate:
            # Clean up the previous assistant message for this thread so it is replaced
            res_thread = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread_obj = res_thread.scalar_one_or_none()
            if thread_obj:
                res_last_msg = await self.db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.thread_id == thread_obj.id)
                    .order_by(ChatMessage.id.desc())
                    .limit(1)
                )
                last_msg = res_last_msg.scalar_one_or_none()
                if last_msg and last_msg.role == "assistant":
                    await self.db.delete(last_msg)
                    await self.db.commit()
        else:
            await self._save_message(session_id, "user", user_message, user_id, user_message)

        # ── Check Pre-computed Semantic QA Cache Fast-Path ──
        semantic_match = await semantic_cache_manager.find_match(user_message)
        if semantic_match:
            sim_score = semantic_match.get("similarity", 0.0)
            direct_threshold = getattr(settings, "SEMANTIC_CACHE_DIRECT_THRESHOLD", 0.80)
            cached_intent = "Diabetes"
            cached_sources = semantic_match.get("sources", [])

            # High similarity (>= 0.80): Serve direct from cache without LLM tailoring, no contribute prompt
            if sim_score >= direct_threshold:
                logger.info(
                    "Semantic cache DIRECT HIT (streaming, sim=%.3f >= %.2f): '%s' -> '%s'. Direct cache without LLM tailoring.",
                    sim_score, direct_threshold, user_message[:40], semantic_match["canonical_question"][:40]
                )
                cached_model = "precomputed-semantic-cache (Direct)"
                cached_answer = semantic_match["answer"]
                can_contribute = False

                tokens = semantic_match.get("tokens") or tokenize_into_stream_tokens(cached_answer)
                total_tokens = 0
                async for event in token_buffer_manager.replay_tokens(tokens, mode=stream_mode, request=request):
                    total_tokens += 1
                    yield event

                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                await self._save_message(session_id, "assistant", cached_answer, user_id)
                await self._update_thread_metadata(session_id, cached_intent, user_query=user_message)

                yield StreamEvent(
                    event="metadata",
                    data=StreamMetadata(
                        thread_id=session_id,
                        total_tokens=total_tokens,
                        execution_time_ms=elapsed_ms,
                        intent=cached_intent,
                        model=cached_model,
                        sources=cached_sources,
                        can_contribute=can_contribute,
                        similarity=sim_score,
                        cached=True,
                        cache_type="semantic_direct",
                        stream_mode=stream_mode,
                    ).model_dump(),
                ).model_dump()
                return

            else:
                # Moderate similarity (< 0.80): Tailor response via LLM according to the user query
                logger.info(
                    "Semantic cache HIT with LLM tailoring (streaming, sim=%.3f < %.2f): '%s' -> '%s'. Tailoring response via LLM...",
                    sim_score, direct_threshold, user_message[:40], semantic_match["canonical_question"][:40]
                )
                from backend.prompts.cache_tailor import CACHE_TAILOR_PROMPT
                from backend.chatbot.hybrid_workflow import model as llm_tailor_model

                cached_model = "precomputed-semantic-cache (LLM Tailored)"
                can_contribute = True
                full_tailored_chunks = []
                total_tokens = 0
                tailor_chain = CACHE_TAILOR_PROMPT | llm_tailor_model

                try:
                    async for chunk in tailor_chain.astream({
                        "query": user_message,
                        "canonical_question": semantic_match["canonical_question"],
                        "cached_answer": semantic_match["answer"],
                    }):
                        if request and await request.is_disconnected():
                            return
                        token_text = chunk.content if hasattr(chunk, "content") else str(chunk)
                        if token_text:
                            full_tailored_chunks.append(token_text)
                            total_tokens += 1
                            yield StreamEvent(
                                event="token",
                                data=StreamTokenData(token=token_text).model_dump(),
                            ).model_dump()

                    tailored_final_text = "".join(full_tailored_chunks)
                except Exception as e:
                    logger.warning("Error during LLM cache tailoring (%s); falling back to raw cached answer", e)
                    tailored_final_text = semantic_match["answer"]
                    yield StreamEvent(
                        event="token",
                        data=StreamTokenData(token=tailored_final_text).model_dump(),
                    ).model_dump()
                    total_tokens = count_tokens(user_message) + count_tokens(tailored_final_text)

                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                await self._save_message(session_id, "assistant", tailored_final_text, user_id)
                await self._update_thread_metadata(session_id, cached_intent, user_query=user_message)

                yield StreamEvent(
                    event="metadata",
                    data=StreamMetadata(
                        thread_id=session_id,
                        total_tokens=total_tokens,
                        execution_time_ms=elapsed_ms,
                        intent=cached_intent,
                        model=cached_model,
                        sources=cached_sources,
                        can_contribute=can_contribute,
                        similarity=sim_score,
                    ).model_dump(),
                ).model_dump()
                return

        # ── Check Redis QA Cache Fast-Path (Exact match for full RAG queries) ──
        qa_cache_key = normalize_query_key(user_message, prefix="rag:qa")
        cached_qa = await cache_manager.get_json(qa_cache_key)
        if cached_qa and isinstance(cached_qa, dict) and cached_qa.get("response") and cached_qa.get("intent") == "Diabetes":
            logger.info("QA cache hit (streaming): '%s'", user_message[:40])
            cached_text = cached_qa["response"]
            cached_intent = cached_qa.get("intent", "Diabetes")
            cached_sources = cached_qa.get("sources", [])
            cached_model = cached_qa.get("model", getattr(active_llm_model, "model_name", "cohere/command-a-reasoning"))

            tokens = cached_qa.get("tokens") or tokenize_into_stream_tokens(cached_text)
            total_tokens = 0
            async for event in token_buffer_manager.replay_tokens(tokens, mode=stream_mode, request=request):
                total_tokens += 1
                yield event

            elapsed_ms = int((time.perf_counter() - start_time) * 1000)
            await self._save_message(session_id, "assistant", cached_text, user_id)
            await self._update_thread_metadata(session_id, cached_intent, user_query=user_message)

            yield StreamEvent(
                event="metadata",
                data=StreamMetadata(
                    thread_id=session_id,
                    total_tokens=total_tokens,
                    execution_time_ms=elapsed_ms,
                    intent=cached_intent,
                    model=cached_model,
                    sources=cached_sources,
                    cached=True,
                    cache_type="qa_exact",
                    stream_mode=stream_mode,
                ).model_dump(),
            ).model_dump()
            return

        graph_config = {"configurable": {"thread_id": active_thread_id}}
        app = await get_chat_app()

        # Retrieve recent conversation history from PostgreSQL ChatMessage
        thread_messages = await self._get_thread_langchain_messages(session_id, limit=12)
        if not thread_messages or thread_messages[-1].content.strip() != user_message.strip():
            thread_messages.append(HumanMessage(content=user_message))

        # Synchronize LangGraph checkpointer state with the database history
        try:
            prev_state = await app.aget_state(graph_config)
            if prev_state and prev_state.values and "messages" in prev_state.values:
                rm_msgs = [RemoveMessage(id=m.id) for m in prev_state.values["messages"] if getattr(m, "id", None)]
                if rm_msgs:
                    await app.aupdate_state(graph_config, {"messages": rm_msgs})
        except Exception as e:
            logger.warning("Could not reset LangGraph checkpointer messages [session=%s]: %s", session_id, e)

        # Extract BYOK headers if provided by client
        custom_api_key = request.headers.get("x-llm-api-key") if request else None
        custom_base_url = request.headers.get("x-llm-base-url") if request else None
        custom_model = request.headers.get("x-llm-model") if request else None
        custom_jina_api_key = request.headers.get("x-jina-api-key") if request else None

        new_input = {
            "messages": thread_messages,
            "query": user_message,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_tokens": max_tokens,
            "reranker_top_n": reranker_top_n,
            "custom_api_key": custom_api_key,
            "custom_base_url": custom_base_url,
            "custom_model": custom_model,
            "custom_jina_api_key": custom_jina_api_key,
        }

        # Nodes whose intermediate outputs we don't want to stream as tokens
        suppress = {
            "router",
            "non_diabetes_node",
            "retrieval_node",
            "summarizer_node",
            "query_rewriter_node",
        }

        app = await get_chat_app()
        full_response: list[str] = []
        total_tokens = 0
        detected_intent = "Diabetes"
        retrieved_sources: list[dict] = []
        semaphore = get_llm_semaphore()

        try:
            async with semaphore:
                async for event in app.astream_events(new_input, config=graph_config, version="v2"):
                    event_type = event.get("event")
                    name = event.get("name", "")
                    node_name = event.get("metadata", {}).get("langgraph_node", "")

                    # ── Capture intent from the router node ──
                    if event_type == "on_chain_end" and node_name == "router":
                        raw_out = event.get("data", {}).get("output", {})
                        out = raw_out if isinstance(raw_out, dict) else {}
                        detected_intent = out.get("intent", "Diabetes")
                        continue

                    # ── Capture retrieved sources from retrieval_node ──
                    if event_type == "on_chain_end" and node_name == "retrieval_node":
                        raw_out = event.get("data", {}).get("output", {})
                        out = raw_out if isinstance(raw_out, dict) else {}
                        retrieved_sources = out.get("sources", [])
                        continue

                    if event_type == "on_chat_model_stream" and node_name not in suppress:
                        chunk = event.get("data", {}).get("chunk")
                        if chunk and hasattr(chunk, "content") and chunk.content:
                            token_text = chunk.content
                            full_response.append(token_text)
                            total_tokens += 1
                            yield StreamEvent(
                                event="token",
                                data=StreamTokenData(token=token_text).model_dump(),
                            ).model_dump()

                    if event_type == "on_chain_end" and node_name == "non_diabetes_node":
                        raw_out = event.get("data", {}).get("output", {})
                        out = raw_out if isinstance(raw_out, dict) else {}
                        rejection_text = out.get("response", "")
                        if rejection_text:
                            full_response.append(rejection_text)
                            total_tokens += len(rejection_text.split())
                            yield StreamEvent(
                                event="token",
                                data=StreamTokenData(token=rejection_text).model_dump(),
                            ).model_dump()

        except asyncio.CancelledError:
            logger.info("Stream cancelled (client disconnect) | session=%s", session_id)
            return
        except Exception as e:
            logger.error("Stream error | session=%s: %s", session_id, e, exc_info=True)
            user_facing_error = format_llm_error_message(e)
            yield StreamEvent(
                event="error",
                data=StreamErrorData(message=user_facing_error).model_dump(),
            ).model_dump()
            return

        # ── Finalise ─────────────────────────────────────────────────────
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        final_text = "".join(full_response)
        total_tokens = max(total_tokens, count_tokens(user_message) + count_tokens(final_text))

        # Persist the assistant response and update thread metadata
        await self._save_message(session_id, "assistant", final_text, user_id)
        await self._update_thread_metadata(session_id, detected_intent, user_query=user_message)

        # Emit closing metadata event
        active_model_name = custom_model or getattr(active_llm_model, "model_name", "cohere/command-a-reasoning")

        # Save to Redis QA cache (TTL: 24h) and Redis Streaming Token Buffer ONLY for valid Diabetes responses
        if final_text and detected_intent == "Diabetes":
            await cache_manager.set_json(
                qa_cache_key,
                {
                    "response": final_text,
                    "tokens": full_response,
                    "intent": detected_intent,
                    "sources": retrieved_sources,
                    "model": active_model_name,
                },
                expire_seconds=86400,
            )
            await token_buffer_manager.store_tokens(
                qa_cache_key,
                tokens=full_response,
                full_text=final_text,
                metadata={
                    "intent": detected_intent,
                    "sources": retrieved_sources,
                    "model": active_model_name,
                },
                expire_seconds=86400,
            )

        yield StreamEvent(
            event="metadata",
            data=StreamMetadata(
                thread_id=session_id,
                total_tokens=total_tokens,
                execution_time_ms=elapsed_ms,
                intent=detected_intent,
                model=active_model_name,
                sources=retrieved_sources,
            ).model_dump(),
        ).model_dump()
    
    async def chat(
        self,
        user_message: str,
        user: User,
        thread_id: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        reranker_top_n: Optional[int] = None,
        is_regenerate: bool = False,
    ) -> ChatResponse:
        start_time = time.perf_counter()
        session_id = thread_id or str(uuid.uuid4())
        active_thread_id = f"user_{user.id}_{session_id}"

        if is_regenerate:
            res_thread = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread_obj = res_thread.scalar_one_or_none()
            if thread_obj:
                res_last_msg = await self.db.execute(
                    select(ChatMessage)
                    .where(ChatMessage.thread_id == thread_obj.id)
                    .order_by(ChatMessage.id.desc())
                    .limit(1)
                )
                last_msg = res_last_msg.scalar_one_or_none()
                if last_msg and last_msg.role == "assistant":
                    await self.db.delete(last_msg)
                    await self.db.commit()
        else:
            await self._save_message(session_id, "user", user_message, user.id, user_message)

        # ── Check Pre-computed Semantic QA Cache Fast-Path ──
        semantic_match = await semantic_cache_manager.find_match(user_message)
        if semantic_match:
            sim_score = semantic_match.get("similarity", 0.0)
            direct_threshold = getattr(settings, "SEMANTIC_CACHE_DIRECT_THRESHOLD", 0.80)
            cached_intent = "Diabetes"
            cached_sources = semantic_match.get("sources", [])

            if sim_score >= direct_threshold:
                logger.info(
                    "Semantic cache DIRECT HIT (sync, sim=%.3f >= %.2f): '%s' -> '%s'. Direct cache without LLM tailoring.",
                    sim_score, direct_threshold, user_message[:40], semantic_match["canonical_question"][:40]
                )
                cached_model = "precomputed-semantic-cache (Direct)"
                cached_answer = semantic_match["answer"]
                can_contribute = False
                execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
                total_tokens = max(1, count_tokens(user_message) + count_tokens(cached_answer))

                await self._save_message(session_id, "assistant", cached_answer, user.id)
                await self._update_thread_metadata(session_id, cached_intent, user_query=user_message)

                return ChatResponse(
                    response=cached_answer,
                    intent=cached_intent,
                    thread_id=session_id,
                    metadata=StreamMetadata(
                        thread_id=session_id,
                        total_tokens=total_tokens,
                        execution_time_ms=execution_time_ms,
                        intent=cached_intent,
                        model=cached_model,
                        sources=cached_sources,
                        can_contribute=can_contribute,
                        similarity=sim_score,
                    ),
                )
            else:
                logger.info(
                    "Semantic cache HIT with LLM tailoring (sync, sim=%.3f < %.2f): '%s' -> '%s'. Tailoring via LLM...",
                    sim_score, direct_threshold, user_message[:40], semantic_match["canonical_question"][:40]
                )
                from backend.prompts.cache_tailor import CACHE_TAILOR_PROMPT
                from backend.chatbot.hybrid_workflow import model as llm_tailor_model

                cached_model = "precomputed-semantic-cache (LLM Tailored)"
                can_contribute = True

                try:
                    tailor_chain = CACHE_TAILOR_PROMPT | llm_tailor_model | StrOutputParser()
                    tailored_text = await tailor_chain.ainvoke({
                        "query": user_message,
                        "canonical_question": semantic_match["canonical_question"],
                        "cached_answer": semantic_match["answer"],
                    })
                except Exception as e:
                    logger.warning("Error during sync cache tailoring: %s; using raw cached answer", e)
                    tailored_text = semantic_match["answer"]

                execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
                total_tokens = max(1, count_tokens(user_message) + count_tokens(tailored_text))

                await self._save_message(session_id, "assistant", tailored_text, user.id)
                await self._update_thread_metadata(session_id, cached_intent, user_query=user_message)

                return ChatResponse(
                    response=tailored_text,
                    intent=cached_intent,
                    thread_id=session_id,
                    metadata=StreamMetadata(
                        thread_id=session_id,
                        total_tokens=total_tokens,
                        execution_time_ms=execution_time_ms,
                        intent=cached_intent,
                        model=cached_model,
                        sources=cached_sources,
                        can_contribute=can_contribute,
                        similarity=sim_score,
                    ),
                )

        # ── Check Redis QA Cache Fast-Path (Exact match for full RAG queries) ──
        qa_cache_key = normalize_query_key(user_message, prefix="rag:qa")
        cached_qa = await cache_manager.get_json(qa_cache_key)
        if cached_qa and isinstance(cached_qa, dict) and cached_qa.get("response") and cached_qa.get("intent") == "Diabetes":
            logger.info("QA cache hit (sync): '%s'", user_message[:40])
            cached_text = cached_qa["response"]
            cached_intent = cached_qa.get("intent", "Diabetes")
            cached_sources = cached_qa.get("sources", [])
            cached_model = cached_qa.get("model", getattr(active_llm_model, "model_name", "cohere/command-a-reasoning"))

            await self._save_message(session_id, "assistant", cached_text, user.id)
            await self._update_thread_metadata(session_id, cached_intent, user_query=user_message)

            execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
            total_tokens = max(1, count_tokens(user_message) + count_tokens(cached_text))

            return ChatResponse(
                response=cached_text,
                intent=cached_intent,
                thread_id=session_id,
                metadata=StreamMetadata(
                    thread_id=session_id,
                    total_tokens=total_tokens,
                    execution_time_ms=execution_time_ms,
                    intent=cached_intent,
                    model=cached_model,
                    sources=cached_sources,
                ),
            )

        graph_config = {"configurable": {"thread_id": active_thread_id}}
        app = await get_chat_app()

        # Retrieve recent conversation history from PostgreSQL ChatMessage
        thread_messages = await self._get_thread_langchain_messages(session_id, limit=12)
        if not thread_messages or thread_messages[-1].content.strip() != user_message.strip():
            thread_messages.append(HumanMessage(content=user_message))

        # Synchronize LangGraph checkpointer state with the database history
        try:
            prev_state = await app.aget_state(graph_config)
            if prev_state and prev_state.values and "messages" in prev_state.values:
                rm_msgs = [RemoveMessage(id=m.id) for m in prev_state.values["messages"] if getattr(m, "id", None)]
                if rm_msgs:
                    await app.aupdate_state(graph_config, {"messages": rm_msgs})
        except Exception as e:
            logger.warning("Could not reset LangGraph checkpointer messages [session=%s]: %s", session_id, e)

        new_input = {
            "messages": thread_messages,
            "query": user_message,
            "temperature": temperature,
            "top_p": top_p,
            "top_k": top_k,
            "max_tokens": max_tokens,
            "reranker_top_n": reranker_top_n,
        }

        semaphore = get_llm_semaphore()
        try:
            async with semaphore:
                final_state = await app.ainvoke(new_input, config=graph_config)
        except Exception as e:
            logger.error("Chat invocation failed [session=%s]: %s", session_id, e, exc_info=True)
            user_facing_error = format_llm_error_message(e)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY if any(c in str(e) for c in ["404", "401", "429", "500", "502", "503"]) else status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=user_facing_error,
            )

        intent = final_state.get("intent", "Diabetes")
        normalized_intent = "Diabetes" if str(intent).lower().strip() == "diabetes" else "Other"
        retrieved_sources = final_state.get("sources", [])

        # Extract assistant response from the final state
        assistant_res = ""
        for msg in reversed(final_state.get("messages", [])):
            if isinstance(msg, AIMessage):
                assistant_res = _extract_text(msg.content)
                if assistant_res:
                    break
        if not assistant_res:
            assistant_res = final_state.get("response", "") or "I apologize, but I could not generate a response. Please try again."

        await self._save_message(session_id, "assistant", assistant_res, user.id)
        await self._update_thread_metadata(session_id, normalized_intent, user_query=user_message)

        execution_time_ms = max(1, int((time.perf_counter() - start_time) * 1000))
        total_tokens = max(1, count_tokens(user_message) + count_tokens(assistant_res))

        active_model_name = getattr(active_llm_model, "model_name", "cohere/command-a-reasoning")

        # Save to Redis QA cache (TTL: 24h) and Redis Streaming Token Buffer ONLY for valid Diabetes responses
        if assistant_res and normalized_intent == "Diabetes":
            sync_tokens = tokenize_into_stream_tokens(assistant_res)
            await cache_manager.set_json(
                qa_cache_key,
                {
                    "response": assistant_res,
                    "tokens": sync_tokens,
                    "intent": normalized_intent,
                    "sources": retrieved_sources,
                    "model": active_model_name,
                },
                expire_seconds=86400,
            )
            await token_buffer_manager.store_tokens(
                qa_cache_key,
                tokens=sync_tokens,
                full_text=assistant_res,
                metadata={
                    "intent": normalized_intent,
                    "sources": retrieved_sources,
                    "model": active_model_name,
                },
                expire_seconds=86400,
            )

        return ChatResponse(
            response=assistant_res,
            intent=normalized_intent,
            thread_id=session_id,
            metadata=StreamMetadata(
                thread_id=session_id,
                total_tokens=total_tokens,
                execution_time_ms=execution_time_ms,
                intent=normalized_intent,
                model=active_model_name,
                sources=retrieved_sources,
            ),
        )
    
    async def regenerate_stream(
        self,
        thread_id: str,
        user: User,
        user_message: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        reranker_top_n: Optional[int] = None,
        request: Optional[Request] = None,
        stream_mode: Optional[str] = "burst",
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Regenerates the assistant response for the query in the thread.
        Displays and saves the query ONLY ONCE in history and replaces the previous assistant answer.
        """
        query_text = (user_message or "").strip()
        if not query_text:
            res_thread = await self.db.execute(
                select(ChatThread).where(
                    ChatThread.thread_id == thread_id,
                    ChatThread.user_id == user.id,
                )
            )
            thread_obj = res_thread.scalar_one_or_none()
            if not thread_obj:
                raise HTTPException(status_code=404, detail="Chat thread not found")

            res_msg = await self.db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == thread_obj.id, ChatMessage.role == "user")
                .order_by(ChatMessage.id.desc())
                .limit(1)
            )
            last_user_msg = res_msg.scalar_one_or_none()
            if not last_user_msg:
                raise HTTPException(status_code=400, detail="No user message found to regenerate")
            query_text = last_user_msg.content

        async for event in self.chat_stream(
            user_message=query_text,
            user=user,
            thread_id=thread_id,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_tokens=max_tokens,
            reranker_top_n=reranker_top_n,
            request=request,
            is_regenerate=True,
            stream_mode=stream_mode,
        ):
            yield event

    async def regenerate(
        self,
        thread_id: str,
        user: User,
        user_message: Optional[str] = None,
        temperature: Optional[float] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        max_tokens: Optional[int] = None,
        reranker_top_n: Optional[int] = None,
    ) -> ChatResponse:
        """
        Synchronous regeneration method.
        """
        query_text = (user_message or "").strip()
        if not query_text:
            res_thread = await self.db.execute(
                select(ChatThread).where(
                    ChatThread.thread_id == thread_id,
                    ChatThread.user_id == user.id,
                )
            )
            thread_obj = res_thread.scalar_one_or_none()
            if not thread_obj:
                raise HTTPException(status_code=404, detail="Chat thread not found")

            res_msg = await self.db.execute(
                select(ChatMessage)
                .where(ChatMessage.thread_id == thread_obj.id, ChatMessage.role == "user")
                .order_by(ChatMessage.id.desc())
                .limit(1)
            )
            last_user_msg = res_msg.scalar_one_or_none()
            if not last_user_msg:
                raise HTTPException(status_code=400, detail="No user message found to regenerate")
            query_text = last_user_msg.content

        return await self.chat(
            user_message=query_text,
            user=user,
            thread_id=thread_id,
            temperature=temperature,
            top_p=top_p,
            top_k=top_k,
            max_tokens=max_tokens,
            reranker_top_n=reranker_top_n,
            is_regenerate=True,
        )

    async def get_history(self, session_id: str, user: User) -> List[MessageSchema]:
        try:
            thread_res = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread = thread_res.scalar_one_or_none()
            if not thread:
                return []
            if thread.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not have permission to view this chat thread.",
                )
            msg_res = await self.db.execute(
                select(ChatMessage).where(
                    ChatMessage.thread_id == thread.id
                ).order_by(ChatMessage.timestamp.asc(), ChatMessage.id.asc())
            )

            raw_messages = list(msg_res.scalars())
            # Deduplicate any consecutive identical user messages from legacy regenerations
            deduped = []
            for m in raw_messages:
                if (
                    m.role == "user"
                    and deduped
                    and deduped[-1].role == "user"
                    and deduped[-1].content.strip() == m.content.strip()
                ):
                    continue
                deduped.append(
                    MessageSchema(role=m.role, content=m.content, timestamp=m.timestamp)
                )

            return deduped
        except Exception as e:
            logger.error("Failed to retrieve history for thread = %s: %s", session_id, e, exc_info=True)
            return []
    
    async def get_threads(self, user: User) -> List[Dict[str, Any]]:
        try:
            res = await self.db.execute(
                select(ChatThread).where(
                    ChatThread.user_id == user.id
                ).order_by(ChatThread.updated_at.desc())
            )
            return [
                {
                    "thread_id": t.thread_id,
                    "preview": t.preview or "New Conversation",
                    "intent": t.intent or "Diabetes",
                    "last_updated": t.updated_at or t.created_at or datetime.now(),
                }
                for t in res.scalars()
            ]
        except Exception as e:
            logger.error("Failed to fetch threads for user = %s: %s", user.id, e, exc_info=True)
            return []
    
    async def delete_chat(self, session_id: str, user: User) -> None:
        try:
            thread_res = await self.db.execute(
                select(ChatThread).where(ChatThread.thread_id == session_id)
            )
            thread = thread_res.scalar_one_or_none()
            if not thread:
                return
            if thread.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Forbidden: You do not have permission to delete this chat thread.",
                )
            await self.db.delete(thread)
            await self.db.commit()
        except HTTPException:
            raise
        except Exception as e:
            logger.error("Failed to delete chat thread=%s: %s", session_id, e)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
    
    async def new_chat(self, user: User, thread_id: Optional[str] = None) -> Dict[str, Any]:
        try:
            new_thread_id = thread_id or str(uuid.uuid4())
            self.db.add(ChatThread(thread_id = new_thread_id, user_id = user.id))
            await self.db.commit()
            return {"thread_id":new_thread_id}
        except Exception as e:
            logger.error("Failed to create new chat for user = %s: %s",user.id, e, exc_info=True)
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

    create_thread = new_chat

    async def contribute_qa(
        self,
        query: str,
        response: str,
        category: Optional[str] = "Community Contributed",
        sources: Optional[List[Dict[str, Any]]] = None,
        user_id: Optional[int] = None,
    ) -> PrecomputedQA:
        """
        Stores a user-contributed Q&A pair in precomputed_qa with Strategy 1 (Semantic Collision
        Detection & Canonical Merging) and Selection Priority (Exact Match + Recency Boost).
        Purges stale Redis match caches and updates the vectorized in-memory index.
        """
        from backend.chatbot.hybrid_workflow import get_embedding_model
        from backend.core.semantic_cache import semantic_cache_manager
        from backend.chatbot.models import PrecomputedQA
        from backend.core.redis import cache_manager, normalize_query_key

        clean_query = query.strip()
        clean_response = response.strip()
        clean_category = (category or "Community Contributed").strip()
        clean_sources = list(sources) if sources else []

        # 1. Compute 768-dim embedding for canonical query matching
        embedder = get_embedding_model()
        emb = embedder.encode(clean_query, show_progress_bar=False).tolist()

        # 2. Strategy 1: Semantic collision detection against existing precomputed Q&As (Option B: Canonical Merging)
        collision_match = await semantic_cache_manager.find_match(
            clean_query,
            query_embedding=emb,
            threshold=0.85,
        )
        if collision_match:
            logger.info(
                "Semantic collision detected during contribution: '%s' aligns with canonical FAQ '%s' [id=%s, sim=%.3f]. "
                "Executing Option B: Canonical Merging (co-existing separate entry with canonical lineage).",
                clean_query[:50],
                collision_match["canonical_question"][:50],
                collision_match["id"],
                collision_match["similarity"],
            )
            # Inherit clinical category if user provided generic placeholder
            if clean_category in ("Community Contributed", "General", "Diabetes") and collision_match.get("category"):
                clean_category = collision_match["category"]
            if not clean_sources and collision_match.get("sources"):
                clean_sources = list(collision_match["sources"])

            # Store canonical lineage tag in sources metadata
            canonical_tag = {
                "canonical_id": collision_match["id"],
                "canonical_question": collision_match["canonical_question"],
                "similarity": collision_match["similarity"],
            }
            if not any(isinstance(s, dict) and s.get("canonical_id") == collision_match["id"] for s in clean_sources):
                clean_sources.append(canonical_tag)

        # 3. Upsert into PostgreSQL precomputed_qa table:
        # If exact string exists, update answer and updated_at.
        # Otherwise, insert as a co-existing separate entry with current timestamp for recency boost.
        res = await self.db.execute(
            select(PrecomputedQA).where(PrecomputedQA.question == clean_query)
        )
        existing = res.scalar_one_or_none()
        now_ts = datetime.utcnow()
        if existing:
            existing.answer = clean_response
            existing.category = clean_category
            existing.sources = clean_sources
            existing.embedding = emb
            existing.is_active = True
            existing.updated_at = now_ts
            target_row = existing
        else:
            new_qa = PrecomputedQA(
                question=clean_query,
                answer=clean_response,
                category=clean_category,
                sources=clean_sources,
                embedding=emb,
                is_active=True,
                created_at=now_ts,
                updated_at=now_ts,
            )
            self.db.add(new_qa)
            target_row = new_qa

        await self.db.commit()
        await self.db.refresh(target_row)

        # 4. Prime Redis cache for fast exact lookup (TTL: 30 days) with token buffer
        q_key = normalize_query_key(clean_query, prefix="rag:precomputed:qa")
        tokens_list = tokenize_into_stream_tokens(target_row.answer)
        await cache_manager.set_json(
            q_key,
            {
                "question": target_row.question,
                "answer": target_row.answer,
                "tokens": tokens_list,
                "category": target_row.category,
                "sources": target_row.sources,
            },
            expire_seconds=2592000,
        )
        await token_buffer_manager.store_tokens(
            q_key,
            tokens=tokens_list,
            full_text=target_row.answer,
            metadata={"category": target_row.category, "sources": target_row.sources},
            expire_seconds=2592000,
        )

        # 5. Invalidate stale semantic query match caches in Redis
        clean_sem_key = normalize_query_key(clean_query, prefix="rag:semantic_match")
        await cache_manager.delete(clean_sem_key)
        if collision_match:
            canon_sem_key = normalize_query_key(collision_match["canonical_question"], prefix="rag:semantic_match")
            await cache_manager.delete(canon_sem_key)
        await cache_manager.delete_pattern("rag:semantic_match:*")

        # 6. Dynamically reload in-memory vectorized matrix with new entry and recency timestamp
        await semantic_cache_manager.load_index(self.db, force=True)
        logger.info(
            "Successfully contributed Q&A [id=%d]: '%s' to precomputed cache (stale Redis caches invalidated).",
            target_row.id,
            clean_query[:50],
        )

        return target_row


