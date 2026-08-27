import json
import logging
from typing import Any, Optional

from app.core.redis import redis


logger = logging.getLogger(__name__)


# =========================================================
# CACHE SERIALIZATION
# =========================================================

def _serialize(value: Any) -> str:
    """
    Convert Python objects into JSON safely.

    default=str handles:
    - UUID
    - datetime
    - date
    - Decimal
    - other non-JSON-native objects
    """
    return json.dumps(
        value,
        default=str,
        separators=(",", ":"),
    )


# =========================================================
# GET CACHE
# =========================================================

def get_cache(key: str) -> Optional[Any]:
    """
    Get value from Redis.

    Returns:
        Cached Python object if available.
        None on cache miss or Redis failure.
    """

    try:
        data = redis.get(key)

        if data is None:
            return None

        # Upstash client can return either a string
        # or bytes depending on configuration/version.
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        return json.loads(data)

    except Exception:
        logger.exception(
            "Redis GET failed for key=%s",
            key,
        )
        return None


# =========================================================
# SET CACHE
# =========================================================

def set_cache(
    key: str,
    value: Any,
    ttl: int = 300,
) -> bool:
    """
    Store value in Redis with TTL.

    Returns:
        True  -> cache successfully stored
        False -> Redis/cache operation failed
    """

    if ttl <= 0:
        return False

    try:
        serialized = _serialize(value)

        redis.set(
            key,
            serialized,
            ex=ttl,
        )

        return True

    except Exception:
        logger.exception(
            "Redis SET failed for key=%s",
            key,
        )
        return False


# =========================================================
# DELETE CACHE
# =========================================================

def delete_cache(key: str) -> bool:
    """
    Delete a single Redis cache key.

    Returns:
        True  -> delete request completed
        False -> Redis operation failed
    """

    try:
        redis.delete(key)
        return True

    except Exception:
        logger.exception(
            "Redis DELETE failed for key=%s",
            key,
        )
        return False