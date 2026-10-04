import asyncio
import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caching_service.db.models import Payload, Transformation
from caching_service.services.payload import PayloadService
from tests.fakes import CountingTransformer

LIST_1 = ["first string", "second string", "third string"]
LIST_2 = ["other string", "another string", "last string"]
EXPECTED = "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"


def make_service(session: AsyncSession, transformer: CountingTransformer) -> PayloadService:
    return PayloadService(session, transformer, max_concurrency=5)


async def test_creates_payload_with_interleaved_transformed_output(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = make_service(session, CountingTransformer())

        result = await service.create(LIST_1, LIST_2)

        assert result.created
        assert await service.get_output(result.id) == EXPECTED


async def test_unknown_payload_has_no_output(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        assert await make_service(session, CountingTransformer()).get_output(uuid.uuid4()) is None


async def test_rejects_lists_of_different_length(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        with pytest.raises(ValueError, match="same length"):
            await make_service(session, CountingTransformer()).create(["a"], [])


async def test_identical_request_reuses_id_without_calling_transformer(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transformer = CountingTransformer()
    async with session_factory() as session:
        service = make_service(session, transformer)
        first = await service.create(LIST_1, LIST_2)
        calls_after_first = len(transformer.calls)

        second = await service.create(LIST_1, LIST_2)

    assert second.id == first.id
    assert not second.created
    assert len(transformer.calls) == calls_after_first


async def test_partially_overlapping_request_transforms_only_new_strings(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transformer = CountingTransformer()
    async with session_factory() as session:
        service = make_service(session, transformer)
        await service.create(["a", "b"], ["c", "d"])
        transformer.calls.clear()

        result = await service.create(["a", "x"], ["c", "y"])

        assert transformer.calls == ["x", "y"]
        assert await service.get_output(result.id) == "A, C, X, Y"


async def test_duplicate_strings_within_request_are_transformed_once(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transformer = CountingTransformer()
    async with session_factory() as session:
        result = await make_service(session, transformer).create(["a", "a"], ["a", "b"])

        assert sorted(transformer.calls) == ["a", "b"]
        assert await make_service(session, transformer).get_output(result.id) == "A, A, A, B"


async def test_swapped_lists_give_a_new_payload_from_cached_transformations(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    transformer = CountingTransformer()
    async with session_factory() as session:
        service = make_service(session, transformer)
        first = await service.create(["a"], ["b"])
        transformer.calls.clear()

        swapped = await service.create(["b"], ["a"])

        assert swapped.id != first.id
        assert transformer.calls == []
        assert await service.get_output(swapped.id) == "B, A"


async def test_transformer_failure_stores_nothing(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        service = make_service(session, CountingTransformer(fail_on="b"))

        with pytest.raises(RuntimeError):
            await service.create(["a"], ["b"])

        assert await session.scalar(select(func.count()).select_from(Payload)) == 0
        assert await session.scalar(select(func.count()).select_from(Transformation)) == 0


async def test_concurrent_identical_requests_resolve_to_one_payload(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def create() -> uuid.UUID:
        async with session_factory() as session:
            return (await make_service(session, CountingTransformer()).create(LIST_1, LIST_2)).id

    ids = await asyncio.gather(*(create() for _ in range(5)))

    assert len(set(ids)) == 1
    async with session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(Payload)) == 1
