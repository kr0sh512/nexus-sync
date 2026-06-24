"""CLI localization (i18n).

User-facing CLI strings are wrapped in :func:`_` so they can be translated.
Log messages (``logger.*``) are intentionally left unwrapped and always stay
in English for grep-ability and operations.

Translation only becomes active after :func:`setup` is called (done in the CLI
entry points). Until then, and whenever no catalog matches the requested
language, ``gettext`` falls back to returning the original (English) message.
"""

from __future__ import annotations

import gettext as _gettext
import os
import sys
from pathlib import Path

DOMAIN = "nexus"
LANG_ENV = "NEXUS_SYNC_LANG"

_translation: _gettext.NullTranslations = _gettext.NullTranslations()


def _locale_dir() -> str:
    """Locate the compiled message catalogs, both in-source and inside a PyInstaller bundle."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled is not None:
        return os.path.join(bundled, "nexus_sync", "locale")
    return str(Path(__file__).resolve().parent / "locale")


def setup(lang: str | None = None) -> None:
    """Activate the message catalog for ``lang``.

    When ``lang`` is ``None`` the ``NEXUS_SYNC_LANG`` env var is consulted, and
    failing that the system locale (``LANGUAGE``/``LANG``/...) is used. Missing
    catalogs fall back silently to the original English strings.
    """
    global _translation
    if lang is None:
        lang = os.environ.get(LANG_ENV) or None
    languages = [lang] if lang else None
    _translation = _gettext.translation(DOMAIN, _locale_dir(), languages=languages, fallback=True)


def gettext(message: str) -> str:
    return _translation.gettext(message)


def ngettext(singular: str, plural: str, n: int) -> str:
    return _translation.ngettext(singular, plural, n)


# Conventional alias used to mark translatable strings; recognized by pybabel.
_ = gettext
