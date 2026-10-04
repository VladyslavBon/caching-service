import asyncio
import logging
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TextIO

import httpx
from pydantic import AliasChoices, ValidationError

from caching_service.cli.runner import CliError, run
from caching_service.cli.settings import STDIO, CliSettings
from caching_service.core.logging import configure_logging

logger = logging.getLogger(__name__)

EXIT_FAILURE = 1
EXIT_USAGE = 2


def _flag_names() -> dict[str, str]:
    """Map each alias to how the user types it, e.g. "r" -> "-r/--repeat"."""
    names: dict[str, str] = {}
    for field in CliSettings.model_fields.values():
        assert isinstance(field.validation_alias, AliasChoices)
        aliases = [a for a in field.validation_alias.choices if isinstance(a, str)]
        display = "/".join(f"-{a}" if len(a) == 1 else f"--{a}" for a in aliases)
        names.update(dict.fromkeys(aliases, display))
    return names


def _validation_messages(error: ValidationError) -> list[str]:
    flags = _flag_names()
    messages = []
    for item in error.errors():
        message = item["msg"].removeprefix("Value error, ")
        location = str(item["loc"][0]) if item["loc"] else None
        messages.append(f"{flags.get(location, location)}: {message}" if location else message)
    return messages


@contextmanager
def _open_output(target: str) -> Iterator[TextIO]:
    if target == STDIO:
        yield sys.stdout
        return
    with open(target, "w", encoding="utf-8") as file:
        yield file


async def _run(settings: CliSettings, out: TextIO) -> None:
    request = settings.load_request()
    async with httpx.AsyncClient(base_url=str(settings.host), timeout=30) as client:
        await run(client, request, settings.repeat, out)


def main(argv: Sequence[str] | None = None) -> int:
    # Results go to stdout/--output; diagnostics go to stderr through logging.
    # force: this is the process entry point, so it owns the logging configuration.
    configure_logging("INFO", fmt="cache-cli: %(levelname)s: %(message)s", force=True)
    try:
        settings = CliSettings(_cli_parse_args=list(argv) if argv is not None else True)
        with _open_output(settings.output) as out:
            asyncio.run(_run(settings, out))
    except ValidationError as error:
        for message in _validation_messages(error):
            logger.error("%s", message)
        return EXIT_USAGE
    except (CliError, OSError) as error:
        logger.error("%s", error)
        return EXIT_FAILURE
    return 0


if __name__ == "__main__":
    sys.exit(main())
