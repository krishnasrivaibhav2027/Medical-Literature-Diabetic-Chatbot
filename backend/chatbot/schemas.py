from typing import Literal, Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class QueryIntent(BaseModel):
    intent: Literal["Diabetes", "Other"] = Field(..., description="The classification intent for this query")

class ChatRequest(BaseModel):
    query: str = Field(..., description = "The text query from the user")
    thread_id: Optional[str] = Field(None, description = "Unique chat thread identifier. If omitted, a new chat thread will be created")
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description="LLM sampling temperature")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="LLM nucleus sampling cutoff")
    top_k: Optional[int] = Field(None, ge=1, le=100, description="LLM top-k vocabulary pool cutoff")
    max_tokens: Optional[int] = Field(None, ge=64, le=8192, description="Maximum tokens to generate")
    reranker_top_n: Optional[int] = Field(None, ge=1, le=50, description="Number of top documents after Cross-Encoder reranking")
    stream_mode: Optional[Literal["burst", "instant", "smooth"]] = Field("burst", description="Streaming playback mode for cached responses: 'burst' (high-speed SSE burst), 'instant' (single payload), or 'smooth' (standard simulated pace)")
    custom_api_key: Optional[str] = Field(None, description="Optional custom BYOK LLM API key")
    custom_base_url: Optional[str] = Field(None, description="Optional custom BYOK LLM API Base URL")
    custom_model: Optional[str] = Field(None, description="Optional custom BYOK model identifier")
    custom_jina_api_key: Optional[str] = Field(None, description="Optional custom BYOK Jina Reranker API key")

class RegenerateRequest(BaseModel):
    thread_id: str = Field(..., description="Unique chat thread identifier to regenerate response for")
    query: Optional[str] = Field(None, description="The query to regenerate response for. If omitted, uses the last user message in the thread")
    temperature: Optional[float] = Field(None, ge=0.0, le=1.0, description="LLM sampling temperature")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="LLM nucleus sampling cutoff")
    top_k: Optional[int] = Field(None, ge=1, le=100, description="LLM top-k vocabulary pool cutoff")
    max_tokens: Optional[int] = Field(None, ge=64, le=8192, description="Maximum tokens to generate")
    reranker_top_n: Optional[int] = Field(None, ge=1, le=50, description="Number of top documents after Cross-Encoder reranking")
    stream_mode: Optional[Literal["burst", "instant", "smooth"]] = Field("burst", description="Streaming playback mode for cached responses: 'burst' (high-speed SSE burst), 'instant' (single payload), or 'smooth' (standard simulated pace)")
    custom_api_key: Optional[str] = Field(None, description="Optional custom BYOK LLM API key")
    custom_base_url: Optional[str] = Field(None, description="Optional custom BYOK LLM API Base URL")
    custom_model: Optional[str] = Field(None, description="Optional custom BYOK model identifier")
    custom_jina_api_key: Optional[str] = Field(None, description="Optional custom BYOK Jina Reranker API key")

class StreamTokenData(BaseModel):
    token: str = Field(..., description = "Streaming Token from the LLM")

class StreamMetadata(BaseModel):
    thread_id: str = Field(..., description = "Thread identifier for this chat")
    total_tokens: int = Field(..., description= "Total number of tokens processed")
    execution_time_ms: int = Field(..., description= "Time in milliseconds for the response generation")
    intent: Literal["Diabetes","Other"] = Field(..., description= "Intent of the query")
    model: Optional[str] = Field("cohere/command-a-reasoning", description="Active underlying LLM model identifier")
    sources: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Retrieved context documents and sources")
    can_contribute: bool = Field(True, description="Whether the user can contribute this response to the precomputed QA table")
    similarity: Optional[float] = Field(None, description="Similarity score with matched precomputed QA if from cache")
    cached: bool = Field(False, description="Whether the response was served from cache")
    cache_type: Optional[str] = Field(None, description="Cache source type ('semantic_direct', 'semantic_tailored', 'qa_exact', 'token_buffer')")
    stream_mode: Optional[str] = Field(None, description="Stream replay mode used ('burst', 'instant', 'smooth', 'live')")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Assistant's final response in markdown")
    intent: str = Field(..., description = "The classified intent for the query(Diabetes or Other)")
    thread_id: str = Field(..., description="Unique chat thread identifier")
    metadata: Optional[StreamMetadata] = Field(None, description="Execution and token usage metadata")

class StreamErrorData(BaseModel):
    message: str = Field(..., description="A user friendly error message")

class StreamEvent(BaseModel):
    event: Literal["token","metadata","interrupt","error"] = Field(..., description = "The type of event")
    data: Dict[str, Any] = Field(..., description = "Event payload containing token, metadata, interrupt, or error data")

class MessageSchema(BaseModel):
    role: str = Field(..., description = "Role of the sender(user, assistant, system)")
    content: str = Field(..., description="Text content of the message")
    timestamp: Optional[datetime] = Field(None, description = "Timestamp of the message")

class HistoryResponse(BaseModel):
    thread_id: str = Field(..., description = "The session/thread identifier")
    messages : List[MessageSchema] = Field(..., description = "Chronological log of chat history")

class ThreadSchema(BaseModel):
    thread_id : str = Field(..., description = "Unique Thread identifier for this chat")
    preview: str = Field(..., description="A short preview of the text")
    intent: Literal["Diabetes", "Other"] = Field(..., description="The classified intent for this query")
    last_updated: datetime = Field(..., description="Timestamp of the last modification")

class ThreadResponse(BaseModel):
    threads: List[ThreadSchema] = Field(..., description="List of available chat threads")

class ContributeQARequest(BaseModel):
    query: str = Field(..., min_length=3, description="The user query to be cached as canonical question")
    response: str = Field(..., min_length=5, description="The assistant's generated response to be stored")
    category: Optional[str] = Field("Community Contributed", description="Clinical topic category")
    sources: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Retrieved sources for the answer")

class ContributeQAResponse(BaseModel):
    status: str = Field("success", description="Status of the contribution operation")
    message: str = Field(..., description="Detailed feedback message")
    id: Optional[int] = Field(None, description="Database ID of the stored precomputed QA record")
    canonical_question: str = Field(..., description="The stored question title")