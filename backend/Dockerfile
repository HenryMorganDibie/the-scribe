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

# Default command runs the API.
#
# The build context is the `backend/` directory (Render: dockerContext=backend
# in render.yaml; Railway: set the service root to backend/), so everything in
# backend/ is copied to /app and the import path is `app.main` — NOT
# `backend.app.main`.
#
# Shell form (sh -c) is required so ${PORT} — injected by Render/Railway — is
# expanded by the shell. In exec form (a JSON array) it would be passed to
# uvicorn as the literal string "${PORT:-8000}" and fail to bind.
#
# Database migrations and scripture seeding run as a separate pre-deploy step
# (see render.yaml `preDeployCommand`), not here — so the web process only ever
# runs uvicorn and stays alive for the health check.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
