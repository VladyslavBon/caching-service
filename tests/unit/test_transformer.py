import asyncio

from caching_service.transformer.batch import transform_many
from caching_service.transformer.simulated import SimulatedTransformer


class RecordingTransformer:
    """Counts calls and the peak number of calls running at the same time."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.running = 0
        self.peak_running = 0

    async def transform(self, value: str) -> str:
        self.calls.append(value)
        self.running += 1
        self.peak_running = max(self.peak_running, self.running)
        await asyncio.sleep(0.01)
        self.running -= 1
        return value.upper()


async def test_simulated_transformer_upper_cases() -> None:
    assert await SimulatedTransformer().transform("first string") == "FIRST STRING"


async def test_transform_many_maps_every_value_to_its_output() -> None:
    result = await transform_many(RecordingTransformer(), ["a", "b"], max_concurrency=2)

    assert result == {"a": "A", "b": "B"}


async def test_transform_many_calls_transformer_once_per_distinct_value() -> None:
    transformer = RecordingTransformer()

    await transform_many(transformer, ["a", "b", "a", "a"], max_concurrency=5)

    assert sorted(transformer.calls) == ["a", "b"]


async def test_transform_many_respects_concurrency_limit() -> None:
    transformer = RecordingTransformer()

    await transform_many(transformer, [str(i) for i in range(10)], max_concurrency=3)

    assert transformer.peak_running == 3


async def test_transform_many_with_no_values_makes_no_calls() -> None:
    transformer = RecordingTransformer()

    assert await transform_many(transformer, [], max_concurrency=3) == {}
    assert transformer.calls == []
