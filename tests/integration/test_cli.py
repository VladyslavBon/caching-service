import io
import json
from collections.abc import AsyncIterator

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from caching_service.api.schemas import PayloadCreateRequest
from caching_service.cli.runner import CliError, run
from caching_service.core.config import Settings
from tests.fakes import CountingTransformer
from tests.helpers import running_client

REQUEST = PayloadCreateRequest(
    list_1=["first string", "second string", "third string"],
    list_2=["other string", "another string", "last string"],
)
EXPECTED = "FIRST STRING, OTHER STRING, SECOND STRING, ANOTHER STRING, THIRD STRING, LAST STRING"


@pytest.fixture
def transformer() -> CountingTransformer:
    return CountingTransformer()


@pytest.fixture
async def client(
    engine: AsyncEngine, settings: Settings, transformer: CountingTransformer
) -> AsyncIterator[AsyncClient]:
    async with running_client(settings, transformer) as client:
        yield client


def results_of(out: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in out.getvalue().splitlines()]


async def test_repeat_reports_one_result_per_iteration(client: AsyncClient) -> None:
    out = io.StringIO()

    await run(client, REQUEST, repeat=3, out=out)

    results = results_of(out)
    assert [r["iteration"] for r in results] == [1, 2, 3]
    assert {r["output"] for r in results} == {EXPECTED}
    assert len({r["id"] for r in results}) == 1


async def test_only_the_first_iteration_creates_the_payload(
    client: AsyncClient, transformer: CountingTransformer
) -> None:
    out = io.StringIO()

    await run(client, REQUEST, repeat=3, out=out)

    assert [r["created"] for r in results_of(out)] == [True, False, False]
    # Six distinct strings, each transformed exactly once across all iterations.
    assert len(transformer.calls) == 6


async def test_server_errors_become_cli_errors(client: AsyncClient) -> None:
    # The service rejects over-long strings; here a NUL byte, which the server refuses.
    request = PayloadCreateRequest.model_construct(list_1=["a\x00"], list_2=["b"])

    with pytest.raises(CliError, match="422"):
        await run(client, request, repeat=1, out=io.StringIO())
