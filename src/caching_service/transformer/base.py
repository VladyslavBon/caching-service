from typing import Protocol


class Transformer(Protocol):
    """Contract of the (external) service that transforms a single string.

    Kept as a protocol so the simulated implementation can be swapped for a real
    HTTP client without touching the caching logic.
    """

    async def transform(self, value: str) -> str: ...
