import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from caching_service.db.dialect import insert_for
from caching_service.db.models import Payload, Transformation
from caching_service.services.hashing import hash_payload_input, hash_text
from caching_service.services.interleave import interleave
from caching_service.transformer.base import Transformer
from caching_service.transformer.batch import transform_many

OUTPUT_SEPARATOR = ", "

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreateResult:
    id: uuid.UUID
    # False when an identical payload already existed and its id was reused.
    created: bool


class PayloadService:
    def __init__(
        self, session: AsyncSession, transformer: Transformer, max_concurrency: int
    ) -> None:
        self._session = session
        self._transformer = transformer
        self._max_concurrency = max_concurrency

    async def create(self, list_1: list[str], list_2: list[str]) -> CreateResult:
        if len(list_1) != len(list_2):
            raise ValueError("Lists must have the same length")

        input_hash = hash_payload_input(list_1, list_2)
        existing_id = await self._find_payload_id(input_hash)
        if existing_id is not None:
            logger.info("Payload %s reused: identical input seen before", existing_id)
            return CreateResult(existing_id, created=False)

        strings = list(dict.fromkeys([*list_1, *list_2]))
        cached = await self._load_cached(strings)
        # Closing the read transaction returns the connection to the pool; holding it
        # while waiting on a slow external service would starve other requests.
        await self._session.commit()

        missing = [s for s in strings if s not in cached]
        fresh = await transform_many(self._transformer, missing, self._max_concurrency)
        outputs = cached | fresh

        output = OUTPUT_SEPARATOR.join(
            interleave([outputs[s] for s in list_1], [outputs[s] for s in list_2])
        )

        await self._store_transformations(fresh)
        payload_id = await self._store_payload(input_hash, list_1, list_2, output)
        await self._session.commit()

        if payload_id is not None:
            # Only counts and ids are logged: the strings themselves may be sensitive.
            logger.info(
                "Payload %s created: %d distinct strings, %d served from cache, %d transformed",
                payload_id,
                len(strings),
                len(cached),
                len(fresh),
            )
            return CreateResult(payload_id, created=True)
        # A concurrent request stored the same payload first; its id is the canonical one.
        winner_id = await self._find_payload_id(input_hash)
        assert winner_id is not None
        logger.info("Payload %s was created concurrently, reusing it", winner_id)
        return CreateResult(winner_id, created=False)

    async def get_output(self, payload_id: uuid.UUID) -> str | None:
        result = await self._session.execute(select(Payload.output).where(Payload.id == payload_id))
        return result.scalar_one_or_none()

    async def _find_payload_id(self, input_hash: str) -> uuid.UUID | None:
        result = await self._session.execute(
            select(Payload.id).where(Payload.input_hash == input_hash)
        )
        return result.scalar_one_or_none()

    async def _load_cached(self, strings: list[str]) -> dict[str, str]:
        hashes = {hash_text(s): s for s in strings}
        result = await self._session.execute(
            select(Transformation.input_hash, Transformation.output).where(
                Transformation.input_hash.in_(hashes)
            )
        )
        return {hashes[input_hash]: output for input_hash, output in result}

    async def _store_transformations(self, fresh: dict[str, str]) -> None:
        if not fresh:
            return
        rows = [
            {"input_hash": hash_text(value), "input": value, "output": output}
            for value, output in fresh.items()
        ]
        # Concurrent requests may have cached the same strings meanwhile; the outputs are
        # deterministic for a given input, so keeping the existing row is correct.
        statement = insert_for(self._session, Transformation).on_conflict_do_nothing(
            index_elements=["input_hash"]
        )
        await self._session.execute(statement, rows)

    async def _store_payload(
        self, input_hash: str, list_1: list[str], list_2: list[str], output: str
    ) -> uuid.UUID | None:
        statement = (
            insert_for(self._session, Payload)
            .values(
                id=uuid.uuid4(),
                input_hash=input_hash,
                list_1=list_1,
                list_2=list_2,
                output=output,
            )
            .on_conflict_do_nothing(index_elements=["input_hash"])
            .returning(Payload.id)
        )
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()
