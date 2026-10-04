import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from caching_service.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Transformation(Base):
    """Cached output of the transformer for a single string.

    Keyed by a hash of the input rather than the input itself: strings can be long and
    a btree index on large text values is bounded in Postgres.
    """

    __tablename__ = "transformations"

    input_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    input: Mapped[str] = mapped_column(Text)
    output: Mapped[str] = mapped_column(Text)


class Payload(Base):
    """A generated payload, deduplicated by the hash of its (ordered) input lists."""

    __tablename__ = "payloads"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # Unique so that identical inputs always resolve to the same payload id, even under
    # concurrent requests: the database, not application code, is the arbiter.
    input_hash: Mapped[str] = mapped_column(String(64), unique=True)
    list_1: Mapped[list[str]] = mapped_column(JSON)
    list_2: Mapped[list[str]] = mapped_column(JSON)
    output: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
