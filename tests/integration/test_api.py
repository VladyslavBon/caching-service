import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from caching_service.core.config import Settings
from tests.fakes import CountingTransformer
from tests.helpers import running_client

BODY = {
    "list_1": ["first string", "second string", "third string"],
    "list_2": ["other string", "another string", "last string"],
}
EXPECTED = "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()


@pytest.fixture
async def client(
    engine: AsyncEngine, settings: Settings, transformer: CountingTransformer
) -> AsyncIterator[AsyncClient]:
    # `engine` guarantees the schema exists before the app starts.
    async with running_client(settings, transformer) as client:
        yield client


async def test_create_then_read_payload(client: AsyncClient) -> None:
    created = await client.post("/payload", json=BODY)

    assert created.status_code == 201
    assert created.json()["message"] == "Payload created"
    payload_id = created.json()["id"]

    read = await client.get(f"/payload/{payload_id}")

    assert read.status_code == 200
    assert read.json() == {"output": EXPECTED}


async def test_resubmitting_same_input_returns_same_id_without_transformer_calls(
    client: AsyncClient, transformer: CountingTransformer
) -> None:
    first = await client.post("/payload", json=BODY)
    calls = len(transformer.calls)

    second = await client.post("/payload", json=BODY)

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert len(transformer.calls) == calls


async def test_unknown_payload_is_not_found(client: AsyncClient) -> None:
    response = await client.get(f"/payload/{uuid.uuid4()}")

    assert response.status_code == 404


async def test_malformed_payload_id_is_rejected(client: AsyncClient) -> None:
    response = await client.get("/payload/not-a-uuid")

    assert response.status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"list_1": ["a"], "list_2": ["b", "c"]},
        {"list_1": [], "list_2": []},
        {"list_1": ["a\x00"], "list_2": ["b"]},
        {"list_1": ["a"]},
        {"list_1": "a", "list_2": ["b"]},
        {"list_1": [1], "list_2": ["b"]},
    ],
    ids=[
        "different-length",
        "empty",
        "nul-character",
        "missing-list",
        "not-a-list",
        "not-a-string",
    ],
)
async def test_invalid_input_is_rejected(client: AsyncClient, body: dict[str, Any]) -> None:
    response = await client.post("/payload", json=body)

    assert response.status_code == 422


async def test_input_over_limits_is_rejected(
    engine: AsyncEngine, settings: Settings, transformer: CountingTransformer
) -> None:
    limited = settings.model_copy(update={"max_list_length": 2, "max_string_length": 3})
    async with running_client(limited, transformer) as client:
        too_many = await client.post(
            "/payload", json={"list_1": list("abc"), "list_2": list("def")}
        )
        too_long = await client.post("/payload", json={"list_1": ["abcd"], "list_2": ["e"]})
        within = await client.post("/payload", json={"list_1": ["abc"], "list_2": ["e"]})

    assert too_many.status_code == 422
    assert too_long.status_code == 422
    assert within.status_code == 201
    assert transformer.calls == ["abc", "e"]


async def test_health(client: AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}
