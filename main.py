from contextlib import asynccontextmanager

import uvicorn
from config import settings
from api.websocket import router as websocket_router
from config import settings
from fastapi import FastAPI
from db.postgres import close_postgres_pool, create_postgres_pool
from db.redis import close_redis_client, create_redis_client
from observability.logging import configure_logging
from observability.metrics import setup_metrics
from observability.tracing import setup_tracing

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    # 1. Logging first — so any errors during the rest of startup are structured.
    configure_logging(settings.log_level)

    # 2. Tracing + metrics providers. Start before resources so connection
    #    setup (pool, redis) is itself traced/instrumented.
    app.state.tracer_provider = setup_tracing(
        service_name=settings.service_name,
        otlp_endpoint=settings.otlp_endpoint,
        insecure=settings.otlp_insecure,
    )
    app.state.meter_provider = setup_metrics(
        service_name=settings.service_name,
        otlp_endpoint=settings.otlp_endpoint,
        insecure=settings.otlp_insecure,
    )

    app.state.postgres_pool = None
    app.state.redis = None
    try:
        app.state.postgres_pool = await create_postgres_pool(settings.postgres_pooler_url)
        app.state.redis = await create_redis_client(settings.redis_url)
        yield
    finally:
        await close_redis_client(app.state.redis)
        await close_postgres_pool(app.state.postgres_pool)
        app.state.meter_provider.shutdown()    # flushes final metric window
        app.state.tracer_provider.shutdown()   # flushes BatchSpanProcessor

app = FastAPI(title="Companion Backend", lifespan=lifespan)
app.include_router(websocket_router)

@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": settings.service_name}

@app.get("/healthz/config")
async def config_check():
    return {"credentials_loaded": bool(settings.google_application_credentials)}

if __name__ == "__main__":
    import os
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8080)),   # Cloud Run injects PORT
        ws_max_size=6 * 1024 * 1024,
        log_config=None,
    )