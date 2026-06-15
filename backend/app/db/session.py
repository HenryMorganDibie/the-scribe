"""
Async database session setup.

connect_args={"statement_cache_size": 0} disables asyncpg's prepared
statement cache. This is required when connecting through a connection
pooler in transaction-pooling mode (e.g. Supabase's pgbouncer pooler, or
Railway's pooled Postgres) — prepared statements can't be reused safely
across pooled connections, and asyncpg's cache otherwise raises
"prepared statement does not exist" errors under load. It's a no-op (and
harmless) against a direct, unpooled Postgres connection such as the local
docker-compose database, so this setting is safe in all environments.
"""
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings


engine = create_async_engine(
    settings.async_database_url,
    echo=settings.ENVIRONMENT == "development",
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    connect_args={"statement_cache_size": 0},
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
