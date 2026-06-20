"""
The Scribe API — application entrypoint.

Run locally:    uvicorn app.main:app --reload --port 8000
Run in prod:    uvicorn app.main:app --host 0.0.0.0 --port $PORT
(see railway.json / Dockerfile for the exact production start command)
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
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
        "environment": settings.ENVIRONMENT,
        "llm_provider": settings.LLM_PROVIDER,
    }


@app.get("/api/health/db")
async def health_db():
    """
    Readiness check — verifies the database connection is alive.
    Useful for confirming DATABASE_URL is correctly wired after deployment.
    """
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        logger.error("health_db_check_failed", error=str(e))
        return JSONResponse(status_code=503, content={"status": "error", "database": "unreachable"})
