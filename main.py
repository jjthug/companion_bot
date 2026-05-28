from contextlib import asynccontextmanager
import os
from config import settings
from api.websocket import router as websocket_router
from config import settings

from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.settings = settings
    yield

app = FastAPI(title="Companion Backend", lifespan=lifespan)
app.include_router(websocket_router)
@app.get("/healthz")
async def healthz():
    return {"status": "ok", "service": settings.service_name}

@app.get("/env")
async def healthz():
    return {"status": "ok", "val": settings.google_application_credentials}

