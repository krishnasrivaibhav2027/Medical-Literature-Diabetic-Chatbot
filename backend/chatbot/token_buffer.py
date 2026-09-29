import re
import time
import json
import asyncio
import logging
from typing import Optional, List, Dict, Any, AsyncGenerator
from fastapi import Request
from backend.core.redis import cache_manager, get_redis_client
from backend.chatbot.schemas import StreamEvent, StreamTokenData

logger = logging.getLogger("app.token_buffer")


def tokenize_into_stream_tokens(text: str) -> List[str]:
    """
    Decomposes full text into streaming token chunks preserving exact whitespace,
    newlines, and punctuation for seamless replay.
    """
    if not text:
        return []
    # Match non-whitespace chunks with trailing whitespace, or standalone whitespace/newlines
    tokens = re.findall(r"\S+\s*|\s+", text)
    return tokens if tokens else [text]


class InFlightBroadcaster:
    """
    Pub/Sub replay broadcaster for in-flight streams.
    Allows concurrent clients requesting the same query to attach to the live stream
    or replay from buffer without triggering redundant LLM calls.
    """

    def __init__(self, query_key: str):
        self.query_key = query_key
        self.buffer: List[str] = []
        self._subscribers: List[asyncio.Queue] = []
        self.done: bool = False
        self.metadata: Optional[Dict[str, Any]] = None
        self.error_msg: Optional[str] = None
        self._lock = asyncio.Lock()

    async def push_token(self, token: str):
        """Append a token and broadcast to all current subscribers."""
        async with self._lock:
            self.buffer.append(token)
            for q in self._subscribers:
                await q.put({"event": "token", "data": {"token": token}})

    async def finish(self, metadata: Dict[str, Any]):
        """Mark stream complete and emit the terminal metadata event to all subscribers."""
        async with self._lock:
            self.done = True
            self.metadata = metadata
            for q in self._subscribers:
                await q.put({"event": "metadata", "data": metadata})
                await q.put(None)  # Sentinel to terminate generator

    async def fail(self, message: str):
        """Mark stream failed and propagate error to subscribers."""
        async with self._lock:
            self.done = True
            self.error_msg = message
            for q in self._subscribers:
                await q.put({"event": "error", "data": {"message": message}})
                await q.put(None)

    async def subscribe(self) -> AsyncGenerator[Dict[str, Any], None]:
        """Subscribe to the broadcaster, replaying buffered tokens first."""
        q = asyncio.Queue()
        async with self._lock:
            # 1. Replay tokens buffered up to this moment
            for tok in self.buffer:
                await q.put({"event": "token", "data": {"token": tok}})
            if self.done:
                if self.error_msg:
                    await q.put({"event": "error", "data": {"message": self.error_msg}})
                elif self.metadata:
                    await q.put({"event": "metadata", "data": self.metadata})
                await q.put(None)
            else:
                self._subscribers.append(q)

        while True:
            item = await q.get()
            if item is None:
                break
            yield item


class TokenBufferManager:
    """
    Manages Redis streaming token caching, high-speed SSE burst replay,
    and in-flight pub/sub broadcast.
    """

    def __init__(self):
        self._broadcasters: Dict[str, InFlightBroadcaster] = {}
        self._broadcaster_lock = asyncio.Lock()

    async def get_or_create_broadcaster(self, query_key: str) -> InFlightBroadcaster:
        async with self._broadcaster_lock:
            if query_key not in self._broadcasters:
                self._broadcasters[query_key] = InFlightBroadcaster(query_key)
            return self._broadcasters[query_key]

    async def get_active_broadcaster(self, query_key: str) -> Optional[InFlightBroadcaster]:
        async with self._broadcaster_lock:
            bc = self._broadcasters.get(query_key)
            if bc and not bc.done:
                return bc
            return None

    async def remove_broadcaster(self, query_key: str):
        async with self._broadcaster_lock:
            self._broadcasters.pop(query_key, None)

    async def store_tokens(
        self,
        query_key: str,
        tokens: List[str],
        full_text: str,
        metadata: Optional[Dict[str, Any]] = None,
        expire_seconds: int = 86400,
    ) -> bool:
        """
        Stores token buffer in Redis under `rag:tokens:<hash>`.
        Also publishes full text to Redis pub/sub channel for cross-worker notification.
        """
        token_key = f"rag:tokens:{query_key.split(':')[-1]}"
        payload = {
            "tokens": tokens,
            "response": full_text,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        success = await cache_manager.set_json(token_key, payload, expire_seconds=expire_seconds)

        # Publish notification on Redis pub/sub channel
        try:
            client = get_redis_client()
            if client:
                channel = f"channel:{token_key}"
                await client.publish(channel, json.dumps({"status": "ready", "token_count": len(tokens)}))
        except Exception as e:
            logger.debug("Redis pub/sub publish skipped: %s", e)

        return success

    async def get_tokens(self, query_key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached token buffer from Redis.
        """
        token_key = f"rag:tokens:{query_key.split(':')[-1]}"
        return await cache_manager.get_json(token_key)

    async def replay_tokens(
        self,
        tokens: List[str],
        mode: str = "burst",
        request: Optional[Request] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Replays tokens as an SSE stream event generator.

        Modes:
        - 'instant': Emits a single consolidated token payload containing the full text in 1 event.
                     Completes in < 2ms without artificial delays.
        - 'burst': Emits tokens in high-speed micro-batches (2-3 tokens) with cooperative
                   asyncio.sleep(0) allowing network sockets to flush at wire speed.
                   Completes a 300-word response in ~30-60ms instead of 3,000ms!
        - 'smooth': Emits tokens with a gentle simulated typing delay (asyncio.sleep(0.008)).
        """
        if not tokens:
            return

        mode_clean = (mode or "burst").lower().strip()

        if mode_clean == "instant":
            full_text = "".join(tokens)
            yield StreamEvent(
                event="token",
                data=StreamTokenData(token=full_text).model_dump(),
            ).model_dump()
            return

        if mode_clean == "burst":
            # High-speed SSE burst: emit in micro-chunks of 2-3 tokens
            chunk_size = 2
            for i in range(0, len(tokens), chunk_size):
                if request and await request.is_disconnected():
                    return
                chunk_str = "".join(tokens[i : i + chunk_size])
                yield StreamEvent(
                    event="token",
                    data=StreamTokenData(token=chunk_str).model_dump(),
                ).model_dump()
                # Yield control to the event loop so the ASGI server flushes the TCP socket immediately
                await asyncio.sleep(0)
            return

        # 'smooth' legacy/slow mode: 1 token at a time with slight pacing
        for token in tokens:
            if request and await request.is_disconnected():
                return
            yield StreamEvent(
                event="token",
                data=StreamTokenData(token=token).model_dump(),
            ).model_dump()
            await asyncio.sleep(0.008)


token_buffer_manager = TokenBufferManager()
