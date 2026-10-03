import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from contextlib import asynccontextmanager

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://sandbox:sandbox@localhost:5432/sandbox_db"
)

engine = create_async_engine(DATABASE_URL, echo=False, pool_pre_ping=True)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def get_db_context():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    if "sqlite" in DATABASE_URL:
        # Test environment: SQLite doesn't support Alembic's async runner cleanly.
        from database.models import Base
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    else:
        import asyncio
        from alembic.config import Config
        from alembic import command
        import os

        cfg_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
        alembic_cfg = Config(os.path.abspath(cfg_path))
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, command.upgrade, alembic_cfg, "head")
