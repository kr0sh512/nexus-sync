import pytest


@pytest.fixture(autouse=True)
def _force_source_locale(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep CLI output in the source language during tests.

    ``nexus-cli`` activates a locale from ``NEXUS_SYNC_LANG`` / the system
    locale, so assertions on English output would break on a machine whose
    locale is, e.g., Russian. Pinning to a language with no catalog makes
    gettext fall back to the source strings regardless of the dev's environment.
    """
    monkeypatch.setenv("NEXUS_SYNC_LANG", "en")
