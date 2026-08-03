import json
from app.core.redis import redis


def get_cache(key: str):
    try:
        data = redis.get(key)
        if data:
            return json.loads(data)
    except Exception:
        pass
    return None


def set_cache(key: str, value, ttl: int = 300):
    try:
        redis.set(key, json.dumps(value), ex=ttl)
    except Exception:
        pass


def delete_cache(key: str):
    try:
        redis.delete(key)
    except Exception:
        pass