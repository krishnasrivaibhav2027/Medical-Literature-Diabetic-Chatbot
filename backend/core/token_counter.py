import logging
from typing import Any, List, Optional, Sequence, Union
import tiktoken
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage, AIMessageChunk
from langchain_core.outputs import ChatGenerationChunk, ChatResult

logger = logging.getLogger("app.token_counter")

_ENCODER: Optional[Any] = None

def get_token_encoder():
    """Lazily load and cache the cl100k_base BPE tokenizer."""
    global _ENCODER
    if _ENCODER is None:
        try:
            _ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning("Failed to load cl100k_base encoder (%s); falling back to gpt-4o", e)
            _ENCODER = tiktoken.encoding_for_model("gpt-4o")
    return _ENCODER

def count_tokens(text_or_messages: Union[str, Sequence[Union[BaseMessage, dict]], None]) -> int:
    """Accurately count tokens using Byte-Pair Encoding (BPE)."""
    if not text_or_messages:
        return 0

    encoder = get_token_encoder()

    if isinstance(text_or_messages, str):
        return len(encoder.encode(text_or_messages))

    total = 0
    if isinstance(text_or_messages, (list, tuple)):
        for item in text_or_messages:
            if hasattr(item, "content"):
                total += len(encoder.encode(str(item.content))) + 4  # Per-message structural overhead
            elif isinstance(item, dict):
                content = item.get("content", "") or item.get("text", "")
                total += len(encoder.encode(str(content))) + 4
            else:
                total += len(encoder.encode(str(item)))
    return total

class TiktokenChatOpenAI(ChatOpenAI):
    """
    ChatOpenAI wrapper that ensures token usage is ALWAYS tracked.
    When upstream providers (like xKiro) stream without the optional final usage chunk,
    this class automatically calculates the BPE tokens using tiktoken and injects
    usage_metadata so that LangSmith and LangGraph capture token counts.
    """

    async def _astream(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Any = None, **kwargs: Any):
        accumulated: List[str] = []
        has_usage = False

        async for chunk in super()._astream(messages, stop=stop, run_manager=run_manager, **kwargs):
            text = chunk.message.content if hasattr(chunk, "message") else getattr(chunk, "text", "")
            if text:
                accumulated.append(text)
            if getattr(getattr(chunk, "message", None), "usage_metadata", None):
                has_usage = True
            yield chunk

        # If the upstream provider did not emit usage metadata, compute via tiktoken
        if not has_usage:
            prompt_text = " ".join(str(m.content) for m in messages)
            in_tokens = count_tokens(prompt_text)
            out_tokens = count_tokens("".join(accumulated))
            total_tokens = in_tokens + out_tokens

            usage = {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "total_tokens": total_tokens,
            }
            final_usage_chunk = ChatGenerationChunk(
                message=AIMessageChunk(
                    content="",
                    usage_metadata=usage,
                    response_metadata={
                        "token_usage": {
                            "prompt_tokens": in_tokens,
                            "completion_tokens": out_tokens,
                            "total_tokens": total_tokens,
                        }
                    },
                )
            )
            if run_manager:
                await run_manager.on_llm_new_token("", chunk=final_usage_chunk)
            yield final_usage_chunk

    async def _agenerate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, run_manager: Any = None, **kwargs: Any) -> ChatResult:
        result: ChatResult = await super()._agenerate(messages, stop=stop, run_manager=run_manager, **kwargs)
        if not result.llm_output or "token_usage" not in result.llm_output:
            prompt_text = " ".join(str(m.content) for m in messages)
            in_tokens = count_tokens(prompt_text)
            out_text = "".join(g.text for g in result.generations)
            out_tokens = count_tokens(out_text)
            total_tokens = in_tokens + out_tokens

            usage = {
                "input_tokens": in_tokens,
                "output_tokens": out_tokens,
                "total_tokens": total_tokens,
            }
            if not result.llm_output:
                result.llm_output = {}
            result.llm_output["token_usage"] = {
                "prompt_tokens": in_tokens,
                "completion_tokens": out_tokens,
                "total_tokens": total_tokens,
            }
            for gen in result.generations:
                if hasattr(gen, "message"):
                    gen.message.usage_metadata = usage
        return result
