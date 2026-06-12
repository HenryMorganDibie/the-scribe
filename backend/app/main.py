from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog

from app.core.config import settings
from app.api.routes import auth, onboarding, projects, voice, generate, export

logger = structlog.get_logger()

app = FastAPI(
    title="The Scribe API",
    description="AI writing assistant for Christian authors — personalized voice, manuscript generation.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
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


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "the-scribe-api"}


@app.on_event("startup")
async def startup():
    logger.info("The Scribe API starting up", environment=settings.ENVIRONMENT)
