import logging

DEFAULT_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"


def configure_logging(
    level: str = "INFO", fmt: str = DEFAULT_FORMAT, *, force: bool = False
) -> None:
    """Send the application's logs to stderr.

    Only the application's own loggers get `level`. The root logger stays at WARNING so
    libraries do not become chatty: with the root at INFO, SQLAlchemy would log every
    SQL statement.

    No-op when the root logger already has handlers (unless `force`), so the host
    process, or the test runner, keeps control of its own configuration.
    """
    logging.basicConfig(level=logging.WARNING, format=fmt, force=force)
    logging.getLogger("caching_service").setLevel(level)
