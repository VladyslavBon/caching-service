"""Delete all cached data, keeping the schema and the migration history.

Uses the application's own settings, so it cleans whichever database the service is
configured for (`.env` / environment) and works the same on every platform.
"""

import asyncio
import logging

from caching_service.core.config import get_settings
from caching_service.core.logging import configure_logging
from caching_service.db.base import Base
from caching_service.db.models import Payload, Transformation  # noqa: F401  (registers tables)
from caching_service.db.session import create_engine

logger = logging.getLogger("caching_service.scripts.clean_db")


async def clean() -> None:
    url = get_settings().async_database_url
    engine = create_engine(url)
    try:
        async with engine.begin() as connection:
            # Reverse dependency order, so a future foreign key cannot block the delete.
            for table in reversed(Base.metadata.sorted_tables):
                result = await connection.execute(table.delete())
                logger.info("Deleted %d rows from %s", result.rowcount, table.name)
    finally:
        await engine.dispose()
    logger.info("Database cleaned: %s", url)


if __name__ == "__main__":
    configure_logging("INFO", fmt="%(message)s")
    asyncio.run(clean())
