from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from typing import AsyncGenerator
from backend.core.config import settings


engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    connect_args={"timeout": 30},
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def ensure_database_exists() -> None:
    """Check if the target database exists in PostgreSQL, and create it if missing."""
    import asyncpg
    from urllib.parse import urlparse
    import logging

    log = logging.getLogger("backend.database")
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    parsed = urlparse(db_url)
    db_name = parsed.path.lstrip("/")

    # Connect to the default 'postgres' maintenance database to check/create the target database
    admin_conn_str = f"postgresql://{parsed.username}:{parsed.password}@{parsed.hostname}:{parsed.port or 5432}/postgres"
    try:
        conn = await asyncpg.connect(admin_conn_str)
        exists = await conn.fetchval("SELECT 1 FROM pg_database WHERE datname = $1", db_name)
        if not exists:
            log.info(f"Database '{db_name}' not found. Creating it automatically...")
            await conn.execute(f'CREATE DATABASE "{db_name}"')
            log.info(f"Database '{db_name}' created successfully.")
        await conn.close()
    except Exception as e:
        log.warning(f"Could not automatically create database '{db_name}': {e}")

async def create_tables() -> None:
    from sqlalchemy import text
    import backend.models  # register User model
    import backend.chatbot.models  # register ChatThread, ChatMessage, PrecomputedQA, DocumentChunk

    await ensure_database_exists()
    async with engine.begin() as conn:
        try:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        except Exception as e:
            import logging
            logging.getLogger("backend.database").warning(
                "Could not enable 'vector' extension automatically: %s. "
                "Ensure pgvector is installed in PostgreSQL.", e
            )
        await conn.run_sync(Base.metadata.create_all)

