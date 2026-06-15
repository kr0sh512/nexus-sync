import logging

import pytest

from nexus_sync.utils.log_config import LOG_LEVEL_ENV, configure_logging


def test_configure_logging_uses_default_info_level(monkeypatch) -> None:
    monkeypatch.delenv(LOG_LEVEL_ENV, raising=False)

    configure_logging()

    assert logging.getLogger().getEffectiveLevel() == logging.INFO


def test_configure_logging_reads_level_from_env(monkeypatch) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV, "debug")

    configure_logging()

    assert logging.getLogger().getEffectiveLevel() == logging.DEBUG


def test_configure_logging_rejects_invalid_level(monkeypatch) -> None:
    monkeypatch.setenv(LOG_LEVEL_ENV, "verbose")

    with pytest.raises(ValueError, match="invalid log level"):
        configure_logging()
