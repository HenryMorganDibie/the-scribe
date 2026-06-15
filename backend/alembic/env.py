"""
Alembic migration environment.

Runs migrations asynchronously against settings.async_database_url (asyncpg).
app.core.config.normalize_db_url() already converts any Postgres scheme
(postgres://, postgresql://, postgresql+asyncpg://) to postgresql+asyncpg://,
so this file does no URL manipulation of its own — it simply uses the same
async engine configuration as app/db/session.py.

connect_args={"statement_cache_size": 0} is required for connection poolers
in transaction-pooling mode (Supabase's pgbouncer, Railway pooled Postgres) —
see app/db/session.py for the full explanation. NullPool is used here (rather
than the session pool settings) because migrations are a single short-lived
connection, not a long-running pool.
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

from app.core.config import settings
from app.db.session import Base
import app.models  # noqa: F401 — ensure all models are registered on Base.metadata

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=settings.async_database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(
        settings.async_database_url,
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
