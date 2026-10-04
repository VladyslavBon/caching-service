import asyncio
import sys
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import TextIO

import httpx
from pydantic import AliasChoices, ValidationError

from caching_service.cli.runner import CliError, run
from caching_service.cli.settings import STDIO, CliSettings

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


def _format_validation_error(error: ValidationError) -> str:
    flags = _flag_names()
    lines = []
    for item in error.errors():
        message = item["msg"].removeprefix("Value error, ")
        location = str(item["loc"][0]) if item["loc"] else None
        lines.append(f"{flags.get(location, location)}: {message}" if location else message)
    return "\n".join(f"cache-cli: error: {line}" for line in lines)


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
    try:
        settings = CliSettings(_cli_parse_args=list(argv) if argv is not None else True)
        with _open_output(settings.output) as out:
            asyncio.run(_run(settings, out))
    except ValidationError as error:
        print(_format_validation_error(error), file=sys.stderr)
        return EXIT_USAGE
    except (CliError, OSError) as error:
        print(f"cache-cli: error: {error}", file=sys.stderr)
        return EXIT_FAILURE
    return 0


if __name__ == "__main__":
    sys.exit(main())
