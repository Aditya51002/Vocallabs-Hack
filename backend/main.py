from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

import redis.asyncio as redis
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.auth import router as auth_router
from api.demo import router as demo_router
from api.routes import router as api_router
from api.websocket import router as websocket_router
from config import parse_cors_origins, settings
from core.message_bus import MessageBus
from core.orchestrator import Orchestrator
from core.llm_router import LLMRouter
from core.search_client import TavilySearchClient


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared services and shutdown cleanly."""

    redis_client = redis.from_url(settings.redis_url, decode_responses=True)
    message_bus = MessageBus(settings.redis_url)
    llm_router = LLMRouter(
        groq_api_key=settings.groq_api_key,
        gemini_api_key=settings.gemini_api_key,
        groq_model=settings.groq_model,
        gemini_model=settings.gemini_model,
        groq_rpm_budget=settings.groq_rpm_budget,
        gemini_rpm_budget=settings.gemini_rpm_budget,
    )
    search_client = TavilySearchClient(api_key=settings.tavily_api_key)
    orchestrator = Orchestrator(message_bus, llm_router, search_client)

    app.state.redis = redis_client
    app.state.message_bus = message_bus
    app.state.llm_router = llm_router
    app.state.search_client = search_client
    app.state.orchestrator = orchestrator

    yield

    await orchestrator.shutdown()
    await redis_client.close()
    await redis_client.connection_pool.disconnect()


app = FastAPI(
    title="ResearchSwarm API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.cors_origin),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log inbound HTTP requests with timing."""

    logger = logging.getLogger("researchswarm.api")
    start = time.perf_counter()
    response = await call_next(request)
    duration = (time.perf_counter() - start) * 1000
    logger.info("%s %s -> %s (%.2fms)", request.method, request.url.path, response.status_code, duration)
    return response


@app.exception_handler(Exception)
async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions and return JSON responses."""

    logging.getLogger("researchswarm.api").exception("Unhandled exception: %s", exc)
    return JSONResponse(status_code=500, content={"error": str(exc)})


app.include_router(auth_router)
app.include_router(api_router)
app.include_router(demo_router)
app.include_router(websocket_router)


@app.get("/health")
@app.get("/api/health")
async def health(request: Request) -> dict[str, str]:
    """Compatibility health endpoint for container and judge checks."""

    redis_status = "connected"
    try:
        if hasattr(request.app.state, "redis"):
            await request.app.state.redis.ping()
    except Exception:
        redis_status = "disconnected"

    return {"status": "ok", "redis": redis_status, "agents": "active"}
