import json
import time
from dataclasses import asdict, dataclass
from typing import TextIO

import httpx

from caching_service.api.schemas import PayloadCreateRequest


class CliError(Exception):
    """A failure to report to the user as a message, not as a traceback."""


@dataclass(frozen=True)
class IterationResult:
    iteration: int
    id: str
    # False when the server recognised the input and reused an existing payload.
    created: bool
    output: str
    elapsed_ms: float


async def run_iteration(
    client: httpx.AsyncClient, request: PayloadCreateRequest, iteration: int
) -> IterationResult:
    started = time.perf_counter()
    created = await client.post("/payload", json=request.model_dump())
    created.raise_for_status()
    payload_id = created.json()["id"]
    read = await client.get(f"/payload/{payload_id}")
    read.raise_for_status()
    elapsed_ms = (time.perf_counter() - started) * 1000
    return IterationResult(
        iteration=iteration,
        id=payload_id,
        created=created.status_code == httpx.codes.CREATED,
        output=read.json()["output"],
        elapsed_ms=round(elapsed_ms, 1),
    )


async def run(
    client: httpx.AsyncClient, request: PayloadCreateRequest, repeat: int, out: TextIO
) -> None:
    """Submit and read back the payload `repeat` times, one JSON line per iteration.

    Repeating makes the cache observable: the first iteration pays for the transformer,
    later ones reuse the stored payload and are much faster.
    """
    for iteration in range(1, repeat + 1):
        try:
            result = await run_iteration(client, request, iteration)
        except httpx.HTTPStatusError as error:
            raise CliError(
                f"server returned {error.response.status_code}: {error.response.text}"
            ) from error
        except httpx.RequestError as error:
            raise CliError(f"cannot reach the server: {error!r}") from error
        # Flush per line so progress is visible while a long run is still going.
        out.write(json.dumps(asdict(result)) + "\n")
        out.flush()
