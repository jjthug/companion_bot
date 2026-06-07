import asyncio
import asyncpg

async def create_postgres_pool(dsn: str):
    return await asyncpg.create_pool(
        dsn=dsn,  # the -pooler hostname
        min_size=2,
        max_size=10,
        command_timeout=60,
        max_inactive_connection_lifetime=300,
        statement_cache_size=0,  # required for PgBouncer transaction mode
    )

async def close_postgres_pool(pool) -> None:
    if pool is None:
        return
    try:
        await asyncio.wait_for(pool.close(), timeout=10)
    except (asyncio.TimeoutError, Exception):
        pool.terminate()  # force-close all connections immediately