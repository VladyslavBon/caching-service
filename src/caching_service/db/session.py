from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


def create_engine(database_url: str | URL) -> AsyncEngine:
    # pool_pre_ping recovers transparently from connections dropped by the server/proxy.
    return create_async_engine(database_url, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    # expire_on_commit=False: objects stay readable after commit without an implicit
    # lazy refresh, which is not possible in async code.
    return async_sessionmaker(engine, expire_on_commit=False)
