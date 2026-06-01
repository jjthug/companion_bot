from redis.asyncio import from_url
from redis.exceptions import RedisError

async def create_redis_client(url: str):
    client = from_url(url, decode_responses=True, max_connections=20,
                      socket_timeout=5, socket_connect_timeout=5,
                      health_check_interval=30)
    await client.ping()  # fail fast at startup if Memorystore is unreachable
    return client

async def close_redis_client(client) -> None:
    if client is None:
        return
    try:
        await client.aclose()
    except (RedisError, OSError):
        pass  # connection already gone; nothing to clean up