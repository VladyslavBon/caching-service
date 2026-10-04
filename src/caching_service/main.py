from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from caching_service.api.routes import router
from caching_service.core.config import Settings, get_settings
from caching_service.db.session import create_engine, create_session_factory
from caching_service.transformer.simulated import SimulatedTransformer


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = create_engine(str(settings.database_url))
        app.state.settings = settings
        app.state.session_factory = create_session_factory(engine)
        app.state.transformer = SimulatedTransformer(settings.transformer_delay_seconds)
        yield
        await engine.dispose()

    app = FastAPI(title="Caching Service", lifespan=lifespan)
    app.include_router(router)
    return app


app = create_app()
