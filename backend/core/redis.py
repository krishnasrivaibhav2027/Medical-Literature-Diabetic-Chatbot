import json
import hashlib
import logging
from typing import Optional, Any
from upstash_redis.asyncio import Redis
from backend.core.config import settings

logger = logging.getLogger("app.redis")

_redis_client: Optional[Redis] = None


def get_redis_client() -> Optional[Redis]:
    """Lazy initialize and return the global Upstash Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        url = getattr(settings, "UPSTASH_REDIS_REST_URL", None)
        token = getattr(settings, "UPSTASH_REDIS_REST_TOKEN", None)
        if not url or not token:
            logger.warning("Upstash Redis credentials are not configured in settings.")
            return None
        try:
            _redis_client = Redis(url=url, token=token)
            logger.info("Initialized Upstash Redis client.")
        except Exception as e:
            logger.error("Failed to initialize Upstash Redis client: %s", e)
            return None
    return _redis_client


def normalize_query_key(query: str, prefix: str = "rag:qa") -> str:
    """Normalize a query string and return a deterministic hashed cache key."""
    normalized = " ".join(query.lower().strip().split())
    query_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}:{query_hash}"


class RedisCacheManager:
    """High-level async Redis cache manager with built-in graceful degradation."""

    @staticmethod
    async def ping() -> bool:
        """Verify Redis connection health."""
        client = get_redis_client()
        if not client:
            return False
        try:
            res = await client.ping()
            return res in ("PONG", True, "pong")
        except Exception as e:
            logger.warning("Redis ping failed: %s", e)
            return False

    @staticmethod
    async def get_str(key: str) -> Optional[str]:
        """Fetch a string value from Redis."""
        client = get_redis_client()
        if not client:
            return None
        try:
            val = await client.get(key)
            if val is not None and not isinstance(val, str):
                val = str(val)
            return val
        except Exception as e:
            logger.warning("Redis get error for key '%s': %s", key, e)
            return None

    @staticmethod
    async def set_str(key: str, value: str, expire_seconds: int = 86400) -> bool:
        """Store a string value in Redis with TTL expiration."""
        client = get_redis_client()
        if not client:
            return False
        try:
            await client.set(key, value, ex=expire_seconds)
            return True
        except Exception as e:
            logger.warning("Redis set error for key '%s': %s", key, e)
            return False

    @staticmethod
    async def get_json(key: str) -> Optional[Any]:
        """Fetch and deserialize a JSON object from Redis."""
        raw = await RedisCacheManager.get_str(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception as e:
            logger.warning("Failed to deserialize JSON for key '%s': %s", key, e)
            return None

    @staticmethod
    async def set_json(key: str, value: Any, expire_seconds: int = 86400) -> bool:
        """Serialize and store a Python dict/list as JSON in Redis with TTL."""
        try:
            serialized = json.dumps(value)
            return await RedisCacheManager.set_str(key, serialized, expire_seconds=expire_seconds)
        except Exception as e:
            logger.warning("Failed to serialize JSON for key '%s': %s", key, e)
            return False

    @staticmethod
    async def delete(key: str) -> bool:
        """Delete a key from Redis."""
        client = get_redis_client()
        if not client:
            return False
        try:
            await client.delete(key)
            return True
        except Exception as e:
            logger.warning("Redis delete error for key '%s': %s", key, e)
            return False

    @staticmethod
    async def delete_pattern(pattern: str) -> int:
        """Delete all keys matching a glob pattern."""
        client = get_redis_client()
        if not client:
            return 0
        try:
            keys = await client.keys(pattern)
            if keys:
                return await client.delete(*keys)
            return 0
        except Exception as e:
            logger.warning("Redis delete_pattern error for pattern '%s': %s", pattern, e)
            return 0


cache_manager = RedisCacheManager()
