from types import SimpleNamespace
from typing import cast

import pytest
from sqlalchemy.dialects.postgresql import Insert as PostgresInsert
from sqlalchemy.dialects.sqlite import Insert as SqliteInsert
from sqlalchemy.ext.asyncio import AsyncSession

from caching_service.db.dialect import insert_for
from caching_service.db.models import Payload


def session_for(dialect_name: str) -> AsyncSession:
    """Just enough of a session for insert_for, which only looks at the dialect name."""
    bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
    return cast(AsyncSession, SimpleNamespace(get_bind=lambda: bind))


def test_postgres_gets_the_postgres_insert() -> None:
    assert isinstance(insert_for(session_for("postgresql"), Payload), PostgresInsert)


def test_sqlite_gets_the_sqlite_insert() -> None:
    assert isinstance(insert_for(session_for("sqlite"), Payload), SqliteInsert)


def test_other_dialects_are_rejected_instead_of_failing_later_in_sql() -> None:
    with pytest.raises(NotImplementedError, match="mysql"):
        insert_for(session_for("mysql"), Payload)
