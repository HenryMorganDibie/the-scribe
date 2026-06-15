"""
Alembic migration environment.

Runs migrations asynchronously against settings.async_database_url (asyncpg) —
this avoids needing psycopg2 as an extra dependency just for migrations.
Works identically against local Postgres+pgvector (docker-compose) and any
managed Postgres (Railway, Supabase) since the URL is normalized in
app.core.config regardless of the scheme the platform provides.
"""

import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

from app.core.config import settings
from app.db.session import Base
import app.models  # noqa: F401 — ensure all models are imported

config = context.config

# Use a safe lookup for SYNC_DATABASE_URL; fall back to deriving a sync URL
# from the async URL by replacing the async driver. We set the config's
# `sqlalchemy.url` differently depending on offline vs online mode so that
# the async engine is never created with a sync driver (psycopg2).
sync_url = getattr(settings, "SYNC_DATABASE_URL", "") or ""
if not sync_url:
    try:
        sync_url = settings.DATABASE_URL.replace("asyncpg", "psycopg2")
    except Exception:
        sync_url = ""

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# If running offline, prefer a sync URL for Alembic's SQL generation.
# If running online, ensure the async URL is used for engine creation.
if context.is_offline_mode():
    offline_url = sync_url or config.get_main_option("sqlalchemy.url")
    if offline_url:
        config.set_main_option("sqlalchemy.url", offline_url)
else:
    async_url = getattr(settings, "DATABASE_URL", "")
    if async_url:
        config.set_main_option("sqlalchemy.url", async_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

DATABASE_URL = settings.DATABASE_URL  # MUST be asyncpg


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},  # see app/db/session.py docstring
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())