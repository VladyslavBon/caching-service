from sqlalchemy.dialects.postgresql import Insert as PostgresInsert
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import Insert as SqliteInsert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from caching_service.db.base import Base


def insert_for(session: AsyncSession, model: type[Base]) -> PostgresInsert | SqliteInsert:
    """INSERT construct that supports ON CONFLICT for the session's dialect.

    The generic SQLAlchemy insert has no upsert support. Postgres is the target database;
    SQLite is supported, so the test suite can run without a database server.
    """
    dialect = session.get_bind().dialect.name
    if dialect == "postgresql":
        return postgres_insert(model)
    if dialect == "sqlite":
        return sqlite_insert(model)
    raise NotImplementedError(f"ON CONFLICT is not supported for dialect {dialect!r}")
