import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.responses import Response

from api.rate_limit import limiter
from database.session import init_db
from api.routes.sandboxes import router as sandboxes_router
from api.routes.auth import router as auth_router
from api.schemas import HealthResponse
from observability.tracing import setup_tracing

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

VERSION = "1.0.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting sandbox API...")
    await init_db()
    logger.info("Database initialized.")
    yield
    logger.info("Shutting down sandbox API.")


app = FastAPI(
    title="E2B-Style Ephemeral Code Sandbox API",
    description="Production-grade API for creating and managing isolated code execution sandboxes.",
    version=VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

setup_tracing(app)

app.include_router(sandboxes_router, prefix="/sandboxes", tags=["sandboxes"])
app.include_router(auth_router, prefix="/auth", tags=["auth"])


@app.get("/health", response_model=HealthResponse, tags=["observability"])
async def health():
    db_status = "ok"
    runtime_status = "ok"
    try:
        from database.session import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception as e:
        logger.warning(f"DB health check failed: {e}")
        db_status = "error"

    try:
        import docker
        docker.from_env().ping()
    except Exception as e:
        logger.warning(f"Docker health check failed: {e}")
        runtime_status = "error"

    overall = "ok" if db_status == "ok" and runtime_status == "ok" else "degraded"
    return HealthResponse(status=overall, database=db_status, runtime=runtime_status, version=VERSION)


@app.get("/metrics", tags=["observability"])
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})
