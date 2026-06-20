"""
Application configuration.

Supports the same DATABASE_URL across environments without code changes:

- Local development (docker-compose Postgres):
  postgresql+asyncpg://scribe:scribe@localhost:5432/thescribe
- Railway / Supabase / any managed Postgres — typically provided as
  "postgresql://..." without a driver suffix.

normalize_db_url() rewrites whatever scheme is provided to use asyncpg, which
is the only driver this app needs (including for Alembic migrations — see
alembic/env.py).
"""
from functools import cached_property
from typing import List
import json
import sys

from pydantic_settings import BaseSettings
from pydantic import field_validator


def normalize_db_url(url: str) -> str:
    """
    Normalize a Postgres URL to use the asyncpg driver, regardless of the
    scheme it was provided with.

    Handles the schemes commonly seen across platforms:
    - "postgres://"            (Heroku/Railway legacy)
    - "postgresql://"          (standard, e.g. Supabase)
    - "postgresql+asyncpg://"  (already correct — passed through)
    """
    if "://" not in url:
        return url

    scheme, rest = url.split("://", 1)
    base_scheme = scheme.split("+")[0]
    if base_scheme == "postgres":
        base_scheme = "postgresql"

    return f"{base_scheme}+asyncpg://{rest}"


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────
    # A single DATABASE_URL is sufficient. Any Postgres scheme works
    # (postgres://, postgresql://, postgresql+asyncpg://) — it's normalized
    # to asyncpg automatically via async_database_url below. This means the
    # same .env structure works for local Docker Postgres, Supabase, and
    # Railway's injected DATABASE_URL without modification.
    DATABASE_URL: str

    # ── Supabase (optional) ──────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_KEY: str = ""

    # ── LLM provider ──────────────────────────────────────────────
    # "anthropic" (production target) or "groq" (free tier, dev/demo)
    LLM_PROVIDER: str = "anthropic"

    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    # ── Auth ──────────────────────────────────────────────────────
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # ── Background jobs / embeddings ────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"

    # ── App ───────────────────────────────────────────────────────
    ENVIRONMENT: str = "development"
    CORS_ORIGINS: str = '["http://localhost:5173"]'
    # Regex of additional allowed origins. Defaults to this project's Vercel
    # deploys (production + branch/preview URLs like
    # the-scribe-git-<branch>-<team>.vercel.app). Set to "" to disable.
    CORS_ORIGIN_REGEX: str = r"https://the-scribe.*\.vercel\.app"
    PORT: int = 8000

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _validate_cors(cls, v: str) -> str:
        try:
            parsed = json.loads(v)
            if not isinstance(parsed, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            raise ValueError(
                f'CORS_ORIGINS must be a JSON array string, e.g. \'["http://localhost:5173"]\'. Got: {v!r}'
            )
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        return json.loads(self.CORS_ORIGINS)

    @cached_property
    def async_database_url(self) -> str:
        """Always returns an asyncpg-driver URL, regardless of input scheme."""
        return normalize_db_url(self.DATABASE_URL)

    def validate_for_startup(self) -> None:
        """
        Fail fast with a clear message if required config is missing for the
        active LLM provider. Called once at app startup.
        """
        problems = []

        if self.LLM_PROVIDER == "anthropic" and not self.ANTHROPIC_API_KEY:
            problems.append(
                "LLM_PROVIDER=anthropic but ANTHROPIC_API_KEY is not set."
            )
        elif self.LLM_PROVIDER == "groq" and not self.GROQ_API_KEY:
            problems.append(
                "LLM_PROVIDER=groq but GROQ_API_KEY is not set."
            )
        elif self.LLM_PROVIDER not in ("anthropic", "groq"):
            problems.append(
                f'LLM_PROVIDER must be "anthropic" or "groq", got {self.LLM_PROVIDER!r}.'
            )

        if self.ENVIRONMENT == "production" and self.SECRET_KEY == "change-me-in-production":
            problems.append(
                "SECRET_KEY is still the default placeholder — set a real secret in production."
            )

        if problems:
            for p in problems:
                print(f"[config error] {p}", file=sys.stderr)
            if self.ENVIRONMENT == "production":
                raise RuntimeError(
                    "Invalid configuration for production startup: " + " | ".join(problems)
                )

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
