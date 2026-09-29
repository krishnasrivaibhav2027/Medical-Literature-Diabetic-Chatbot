import json
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.responses import StreamingResponse
from backend.auth.dependencies import get_current_user
from backend.users.models import User
from backend.chatbot.service import ChatbotService
from backend.chatbot.schemas import (
    ChatRequest,
    RegenerateRequest,
    ChatResponse,
    HistoryResponse,
    ThreadSchema,
    ThreadResponse,
    ContributeQARequest,
    ContributeQAResponse,
)
import logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix = "/chatbot", tags=["chatbot"])

@router.post("/new-chat",status_code=status.HTTP_201_CREATED)
async def new_chat(current_user: User = Depends(get_current_user),chatbot_service: ChatbotService = Depends()):
    try:
        return await chatbot_service.new_chat(current_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred creating new chat: {str(e)}",
        )

@router.post("/chat")
async def chat(
    request: Request, 
    chat_request: ChatRequest,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends(),
) -> StreamingResponse:
    stream_mode = request.headers.get("x-stream-mode") or chat_request.stream_mode or "burst"

    async def event_generator():
        async for event in chatbot_service.chat_stream(
            user_message = chat_request.query,
            user = current_user,
            thread_id=chat_request.thread_id,
            temperature=chat_request.temperature,
            top_p=chat_request.top_p,
            top_k=chat_request.top_k,
            max_tokens=chat_request.max_tokens,
            reranker_top_n=chat_request.reranker_top_n,
            request = request,
            stream_mode = stream_mode,
        ):
            if await request.is_disconnected():
                break
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/chat/sync", response_model = ChatResponse, status_code=status.HTTP_200_OK)
async def chat_sync(
    request: ChatRequest,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends()
) -> ChatResponse:
    return await chatbot_service.chat(
        user_message=request.query,
        user=current_user,
        thread_id=request.thread_id,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        max_tokens=request.max_tokens,
        reranker_top_n=request.reranker_top_n,
    )

@router.post("/regenerate")
async def regenerate(
    request: Request,
    regen_request: RegenerateRequest,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends(),
) -> StreamingResponse:
    """
    Regenerates the response for the specified chat thread.
    Streams SSE tokens and replaces the previous assistant answer without duplicating the user query.
    """
    stream_mode = request.headers.get("x-stream-mode") or regen_request.stream_mode or "burst"

    async def event_generator():
        async for event in chatbot_service.regenerate_stream(
            thread_id=regen_request.thread_id,
            user=current_user,
            user_message=regen_request.query,
            temperature=regen_request.temperature,
            top_p=regen_request.top_p,
            top_k=regen_request.top_k,
            max_tokens=regen_request.max_tokens,
            reranker_top_n=regen_request.reranker_top_n,
            request=request,
            stream_mode=stream_mode,
        ):
            if await request.is_disconnected():
                break
            yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/regenerate/sync", response_model=ChatResponse, status_code=status.HTTP_200_OK)
async def regenerate_sync(
    request: RegenerateRequest,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends(),
) -> ChatResponse:
    """Synchronous regeneration endpoint."""
    return await chatbot_service.regenerate(
        thread_id=request.thread_id,
        user=current_user,
        user_message=request.query,
        temperature=request.temperature,
        top_p=request.top_p,
        top_k=request.top_k,
        max_tokens=request.max_tokens,
        reranker_top_n=request.reranker_top_n,
    )

@router.get('/threads', response_model=ThreadResponse, status_code=status.HTTP_200_OK)
async def get_threads(
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends()
) -> ThreadResponse:
    try:
        threads = await chatbot_service.get_threads(current_user)
        thread_schemas = [ThreadSchema(**thread) for thread in threads]
        return ThreadResponse(threads=thread_schemas)
    except Exception as e:
        logger.error("Failed retrieving threads: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred retrieving threads: {str(e)}",
        )

@router.get("/history/{thread_id}", response_model = HistoryResponse, status_code=status.HTTP_200_OK)
async def get_history(
    thread_id: str,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends()
) -> HistoryResponse:
    try:
        messages = await chatbot_service.get_history(thread_id, current_user)
        return HistoryResponse(thread_id=thread_id, messages=messages)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred retrieving history: {str(e)}",
        )
    
@router.delete("/delete-chat/{thread_id}",status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat(thread_id: str, current_user: User = Depends(get_current_user),chatbot_service: ChatbotService = Depends()):
    try:
        await chatbot_service.delete_chat(thread_id, current_user)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred deleting chat: {str(e)}",
        )

@router.get("/model-info", status_code=status.HTTP_200_OK)
async def get_model_info():
    """Returns the currently active underlying LLM model and provider dynamically configured on the backend."""
    from backend.chatbot.hybrid_workflow import model
    model_name = getattr(model, "model_name", "cohere/command-a-reasoning")
    base_url = str(getattr(model, "base_url", getattr(model, "openai_api_base", ""))).lower()
    
    if "xkiro" in base_url:
        provider = "Xkiro Cloud API"
    elif "nvidia" in base_url:
        provider = "NVIDIA Cloud API"
    elif "groq" in base_url:
        provider = "Groq Cloud API"
    else:
        provider = "LLM Cloud API"

    return {
        "model": model_name,
        "provider": provider,
        "embedding_model": "google/embeddinggemma-300m",
    }


@router.post("/contribute-response", response_model=ContributeQAResponse, status_code=status.HTTP_201_CREATED)
async def contribute_response(
    payload: ContributeQARequest,
    current_user: User = Depends(get_current_user),
    chatbot_service: ChatbotService = Depends(),
) -> ContributeQAResponse:
    """
    User contribution endpoint:
    Stores the user-verified query and generated answer in the precomputed QA table,
    primes Upstash Redis, and updates the in-memory semantic cache for instantaneous matching.
    """
    try:
        qa_row = await chatbot_service.contribute_qa(
            query=payload.query,
            response=payload.response,
            category=payload.category or "Community Contributed",
            sources=payload.sources,
            user_id=current_user.id,
        )
        return ContributeQAResponse(
            status="success",
            message="Response successfully contributed to the pre-computed clinical cache for faster responses.",
            id=qa_row.id,
            canonical_question=qa_row.question,
        )
    except Exception as e:
        logger.error("Failed to contribute response: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred saving contributed response: {str(e)}",
        )



