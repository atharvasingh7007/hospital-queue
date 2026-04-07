"""
Hospital Queue AI — Main Application
FastAPI entry point with middleware, CORS, and route registration.
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from core.config import AppConfig
from database import init_db, dispose_db
from routes import router

# ── Logging ────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("hospital_queue")

# ── Rate limiter ───────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


# ── App lifecycle ──────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Hospital Queue AI...")

    try:
        await init_db()
        logger.info("Database tables ready")
    except Exception as exc:
        logger.error("Database init failed: %s", exc)

    gcp_status = "available" if AppConfig.has_gcp_credentials() else "not configured (fallback mode)"
    logger.info("GCP credentials: %s", gcp_status)
    logger.info("Hospital Queue AI is running")

    yield

    logger.info("Shutting down...")
    await dispose_db()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Hospital Queue AI",
        description="Multi-Agent Hospital Queue Management System",
        version="1.0.0",
        docs_url="/docs" if AppConfig.DEBUG else None,
        lifespan=lifespan,
    )

    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS — allow frontend dev servers
    app.add_middleware(
        CORSMiddleware,
        allow_origins=AppConfig.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        max_age=600,
    )

    # Security headers
    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    # Request logging
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        request_id = str(uuid.uuid4())[:8]
        start = time.perf_counter()
        logger.info("[%s] %s %s", request_id, request.method, request.url.path)

        response = await call_next(request)

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        logger.info("[%s] %s | %dms", request_id, response.status_code, elapsed_ms)
        response.headers["X-Request-ID"] = request_id
        return response

    # Register routes
    app.include_router(router)

    @app.get("/")
    async def root():
        return {
            "name": "Hospital Queue AI",
            "version": "1.0.0",
            "status": "running",
            "description": "Multi-Agent Hospital Queue Management System",
        }

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=AppConfig.DEBUG,
        workers=1,
        log_level="info",
    )
