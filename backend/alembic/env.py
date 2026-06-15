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
from sqlalchemy.ext.asyncio import create_async_engine
from alembic import context

from app.core.config import settings
from app.db.session import Base
import app.models  # noqa: F401 — ensure all models are registered

config = context.config
config.set_main_option("sqlalchemy.url", settings.async_database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    connectable = create_async_engine(
        settings.async_database_url,
        poolclass=pool.NullPool,
        connect_args={"statement_cache_size": 0},  # 👈 FIX FOR PGBOUNCER
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
