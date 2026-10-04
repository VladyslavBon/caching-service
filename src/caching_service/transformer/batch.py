import asyncio
from collections.abc import Iterable

from caching_service.transformer.base import Transformer


async def transform_many(
    transformer: Transformer, values: Iterable[str], max_concurrency: int
) -> dict[str, str]:
    """Transform each distinct value once, with bounded parallelism.

    Duplicates are collapsed because the transformer is an expensive resource;
    the bound protects the external service from being flooded by a large batch.
    """
    unique_values = list(dict.fromkeys(values))
    semaphore = asyncio.Semaphore(max_concurrency)

    async def run(value: str) -> str:
        async with semaphore:
            return await transformer.transform(value)

    outputs = await asyncio.gather(*(run(value) for value in unique_values))
    return dict(zip(unique_values, outputs, strict=True))
