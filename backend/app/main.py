from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes import router
from app.config import settings
from app.db import new_engine, session_factory
from app.storage.files import get_storage

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = new_engine()
    app.state.engine = engine
    app.state.session_factory = session_factory(engine)
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=True)
    app.state.http = httpx.AsyncClient(timeout=settings.http_timeout_seconds)
    await app.state.redis.ping()
    if settings.storage_backend == "s3":
        storage = get_storage()
        await __import__("asyncio").to_thread(storage.ensure_bucket)
    else:
        settings.storage_path.mkdir(parents=True, exist_ok=True)
    yield
    await app.state.http.aclose()
    await app.state.redis.aclose()
    await engine.dispose()


app = FastAPI(title="ResearchOS", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.exception_handler(Exception)
async def unhandled(request, exc: Exception):
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    logger.exception("unhandled error")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
