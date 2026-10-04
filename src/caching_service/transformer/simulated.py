import asyncio


class SimulatedTransformer:
    """Stand-in for the external service: upper-cases the input after a fixed delay.

    The delay makes the cost of a call visible, so cache hits are observable.
    """

    def __init__(self, delay_seconds: float = 0.0) -> None:
        self._delay_seconds = delay_seconds

    async def transform(self, value: str) -> str:
        await asyncio.sleep(self._delay_seconds)
        return value.upper()
