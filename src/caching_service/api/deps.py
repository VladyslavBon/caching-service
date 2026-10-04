from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from caching_service.core.config import Settings
from caching_service.services.payload import PayloadService
from caching_service.transformer.base import Transformer

# Shared resources live on app.state (built in the lifespan) instead of module globals,
# so every app instance, e.g. one per test, owns its own engine and settings.


def get_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_transformer(request: Request) -> Transformer:
    transformer: Transformer = request.app.state.transformer
    return transformer


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    async with factory() as session:
        yield session


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_payload_service(
    session: Annotated[AsyncSession, Depends(get_session)],
    transformer: Annotated[Transformer, Depends(get_transformer)],
    settings: SettingsDep,
) -> PayloadService:
    return PayloadService(session, transformer, settings.transformer_max_concurrency)


PayloadServiceDep = Annotated[PayloadService, Depends(get_payload_service)]
