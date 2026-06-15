import logging
import os

LOG_LEVEL_ENV = "NEXUS_SYNC_LOG_LEVEL"
DEFAULT_LOG_LEVEL = "INFO"
DEFAULT_LOG_FORMAT = "%(levelname)s %(name)s %(message)s"


def configure_logging(level: str | None = None) -> None:
    raw_level = level or os.environ.get(LOG_LEVEL_ENV, DEFAULT_LOG_LEVEL)
    log_level = getattr(logging, raw_level.upper(), None)
    if not isinstance(log_level, int):
        raise ValueError(f"invalid log level: {raw_level}")

    logging.basicConfig(
        level=log_level,
        format=DEFAULT_LOG_FORMAT,
    )
    logging.getLogger().setLevel(log_level)
