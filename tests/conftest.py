import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from caching_service.core.config import Settings
from caching_service.db.base import Base
from caching_service.db.session import create_engine, create_session_factory


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    # SQLite keeps the suite runnable anywhere; TEST_DATABASE_URL points it at Postgres
    # to verify behaviour (notably concurrency) on the production database.
    return os.environ.get("TEST_DATABASE_URL") or f"sqlite+aiosqlite:///{tmp_path.as_posix()}/t.db"


@pytest.fixture
def settings(database_url: str) -> Settings:
    return Settings(database_url=database_url, transformer_delay_seconds=0)


@pytest.fixture
async def engine(database_url: str) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return create_session_factory(engine)
