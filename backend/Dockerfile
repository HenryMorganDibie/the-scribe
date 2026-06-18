# The Scribe API — production image.
#
# Used by Railway (and any Docker-based host) for both the API service and
# the worker service — they share this image with different start commands
# (see railway.json / README "Deploying" section).
#
# Local development does NOT use this image — see docker-compose.yml, which
# only provides Postgres+pgvector and Redis. The API and worker run directly
# via uvicorn/dramatiq in a local virtualenv for faster iteration.

FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps: build tools for any packages that need compilation,
# libpq for asyncpg/psycopg-adjacent native bits.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

# Pre-download the embedding model at build time so the first request/job
# doesn't pay the ~90MB download cost in production.
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

EXPOSE 8000

# Default command runs the full production startup: migrate, seed, serve.
# Written in shell form (not exec-form array) so that:
#   1. $PORT is properly expanded by the shell at container runtime (Railway
#      injects this dynamically -- exec-form CMD ["..."] arrays do NOT invoke
#      a shell, so "${PORT:-8000}" inside a JSON array is passed to uvicorn
#      as a literal, unexpanded string, and uvicorn fails to parse it as a
#      port and exits immediately).
#   2. The migrate -> seed -> serve sequence runs as one chained command.
# This mirrors railway.json's startCommand exactly, so the correct command
# runs whether Railway reads railway.json or falls back to this Dockerfile's
# CMD. The worker service overrides this entirely via its own start command
# (dramatiq app.workers.tasks) set in the Railway dashboard.
CMD alembic upgrade head && python scripts/seed_scriptures.py && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
