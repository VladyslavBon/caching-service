class CountingTransformer:
    """Upper-cases like the real transformer and records every call it receives."""

    def __init__(self, fail_on: str | None = None) -> None:
        self.calls: list[str] = []
        self._fail_on = fail_on

    async def transform(self, value: str) -> str:
        self.calls.append(value)
        if value == self._fail_on:
            raise RuntimeError("transformer unavailable")
        return value.upper()
