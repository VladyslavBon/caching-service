from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from httpx import ASGITransport, AsyncClient

from caching_service.api.deps import get_transformer
from caching_service.core.config import Settings
from caching_service.main import create_app
from caching_service.transformer.base import Transformer


@asynccontextmanager
async def running_client(
    settings: Settings, transformer: Transformer | None = None
) -> AsyncIterator[AsyncClient]:
    """HTTP client bound to a fully started app (lifespan included, as ASGITransport skips it)."""
    app = create_app(settings)
    if transformer is not None:
        app.dependency_overrides[get_transformer] = lambda: transformer
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client
