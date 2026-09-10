"""
The Scribe API — application entrypoint.

Run locally:    uvicorn app.main:app --reload --port 8000
Run in prod:    uvicorn app.main:app --host 0.0.0.0 --port $PORT
(see railway.json / Dockerfile for the exact production start command)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import settings
from app.db.session import engine
from app.api.routes import auth, onboarding, projects, voice, generate, export, sermons

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Plain print (not structlog) so this line is guaranteed to appear even
    # if structlog's own configuration is somehow the thing that's broken --
    # this is the very first line of app code that runs, before any
    # validation. If this line never appears in deploy logs, the process
    # didn't even reach Python startup (a Dockerfile/start-command issue).
    # If this line appears but nothing after it does, validate_for_startup()
    # raised -- check CONFIG ERROR lines immediately below it.
    print("[STARTUP] Entering FastAPI lifespan -- about to validate config...", flush=True)
    settings.validate_for_startup()
    print("[STARTUP] Config validated OK.", flush=True)

    # Eagerly load the fastembed ONNX model so the first user doesn't pay the
    # download/init cost (30-90s on a cold instance) during voice DNA extraction.
    print("[STARTUP] Warming up embedding model...", flush=True)
    try:
        import asyncio
        from app.services.voice.embeddings import _load_model
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _load_model)
        print("[STARTUP] Embedding model ready.", flush=True)
    except Exception as e:
        # Non-fatal — embedding still works, just slower on first call
        print(f"[STARTUP] Embedding model warmup failed (non-fatal): {e}", flush=True)

    logger.info(
        "the_scribe_api_starting",
        environment=settings.ENVIRONMENT,
        llm_provider=settings.LLM_PROVIDER,
    )
    yield
    await engine.dispose()
    logger.info("the_scribe_api_shutdown")


app = FastAPI(
    title="The Scribe API",
    description="AI writing assistant for Christian authors — personalized voice, manuscript generation.",
    version="1.0.0",
    docs_url=None if settings.ENVIRONMENT == "production" else "/api/docs",
    redoc_url=None if settings.ENVIRONMENT == "production" else "/api/redoc",
    lifespan=lifespan,
)

# CORS
# allow_origins handles the explicit list (e.g. localhost in dev); allow_origin_regex
# matches the project's Vercel deploys (production + the auto-generated branch/preview
# URLs) so we don't have to hard-code every changing preview domain.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=settings.CORS_ORIGIN_REGEX or None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    """Defense-in-depth headers and an early cap on oversized requests."""
    content_length = request.headers.get("content-length")
    if content_length and request.method in {"POST", "PUT", "PATCH"}:
        try:
            if int(content_length) > settings.MAX_UPLOAD_BYTES + 1024 * 1024:
                return JSONResponse(status_code=413, content={"detail": "Request body is too large."})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Content-Security-Policy", "frame-ancestors 'none'")
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    if settings.ENVIRONMENT == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response

# Routes
app.include_router(auth.router, prefix="/api")
app.include_router(onboarding.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(generate.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(sermons.router, prefix="/api")


@app.get("/api/health")
async def health():
    """
    Liveness check — used by Railway/Docker health checks.
    Returns service status and confirms config/LLM provider, without
    making an external API call.
    """
    return {
        "status": "ok",
        "service": "the-scribe-api",
    }


@app.get("/api/health/db")
async def health_db():
    """
    Readiness check — verifies the database connection is alive.
    Useful for confirming DATABASE_URL is correctly wired after deployment.
    """
    from sqlalchemy import text
    from fastapi import HTTPException

    if settings.ENVIRONMENT == "production":
        raise HTTPException(status_code=404, detail="Not found")

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error("health_db_check_failed", error=str(e))
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
