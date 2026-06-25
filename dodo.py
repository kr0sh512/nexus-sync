import os
import sys
from pathlib import Path

DOIT_CONFIG = {
    "default_tasks": ["test", "typecheck", "format_check", "wheel"],
}

PYTHON = sys.executable
PYBABEL = f"{PYTHON} -m babel.messages.frontend"
SPHINX = f"{PYTHON} -m sphinx"
PACKAGE_VERSION = "0.1.0"
WHEEL_TARGET = f"dist/nexus_sync-{PACKAGE_VERSION}-py3-none-any.whl"
SRC_FILES = list(Path("src").rglob("*.py"))
TEST_FILES = list(Path("tests").rglob("*.py"))
DOC_FILES = [Path("README.md"), *Path("docs").glob("*.md")]
BUILD_DEPS = [Path("pyproject.toml"), Path("README.md"), *SRC_FILES]

# Localization (nexus-cli catalogs only; daemon/server logs stay in English).
LOCALE_DIR = Path("src/nexus_sync/locale")
POT_FILE = LOCALE_DIR / "nexus.pot"
PO_FILES = sorted(LOCALE_DIR.rglob("*.po"))
MO_FILES = [po.with_suffix(".mo") for po in PO_FILES]
# PyInstaller --add-data separator: ';' on Windows, ':' elsewhere.
LOCALE_DATA = f"{LOCALE_DIR}{';' if os.name == 'nt' else ':'}nexus_sync/locale"

# Documentation (Sphinx).
DOCS_DIR = Path("docs")
DOCS_HTML = DOCS_DIR / "_build" / "html"


def task_test():
    return {
        "actions": [f"{PYTHON} -m pytest -q"],
        "file_dep": [str(path) for path in [*SRC_FILES, *TEST_FILES]],
        "verbosity": 2,
    }


def task_typecheck():
    return {
        "actions": [f"{PYTHON} -m mypy src"],
        "file_dep": [str(path) for path in SRC_FILES],
        "verbosity": 2,
    }


def task_format_check():
    return {
        "actions": [f"{PYTHON} -m black --check ."],
        "file_dep": [str(path) for path in [*SRC_FILES, *TEST_FILES, Path("dodo.py")]],
        "verbosity": 2,
    }


def task_i18n_extract():
    """Rebuild the .pot template from strings wrapped in _()/gettext()/ngettext()."""
    return {
        "actions": [f"{PYBABEL} extract -F babel.cfg -k _ -o {POT_FILE} src"],
        "file_dep": [str(path) for path in SRC_FILES] + ["babel.cfg"],
        "targets": [str(POT_FILE)],
        "verbosity": 2,
    }


def task_i18n_init():
    """Create a catalog for a new language, e.g. `doit i18n_init --lang de`."""
    return {
        "actions": [f"{PYBABEL} init -i {POT_FILE} -d {LOCALE_DIR} -D nexus -l %(lang)s"],
        "params": [{"name": "lang", "short": "l", "long": "lang", "default": "ru"}],
        "file_dep": [str(POT_FILE)],
        "verbosity": 2,
    }


def task_i18n_update():
    """Merge new/changed strings from the template into existing catalogs."""
    return {
        "actions": [f"{PYBABEL} update -i {POT_FILE} -d {LOCALE_DIR} -D nexus"],
        "file_dep": [str(POT_FILE)],
        "verbosity": 2,
    }


def task_i18n_compile():
    """Compile .po catalogs into the .mo files bundled with nexus-cli."""
    return {
        "actions": [f"{PYBABEL} compile -d {LOCALE_DIR} -D nexus"],
        "file_dep": [str(path) for path in PO_FILES],
        "targets": [str(path) for path in MO_FILES],
        "clean": True,
        "verbosity": 2,
    }


def task_docs():
    """Build the Sphinx HTML documentation (warnings are errors)."""
    return {
        "actions": [f"{SPHINX} -b html -W --keep-going {DOCS_DIR} {DOCS_HTML}"],
        "file_dep": [str(path) for path in [*DOC_FILES, DOCS_DIR / "conf.py", *SRC_FILES]],
        "targets": [str(DOCS_HTML / "index.html")],
        "clean": ["rm -rf docs/_build"],
        "verbosity": 2,
    }


def task_wheel():
    return {
        "actions": [f"{PYTHON} -m build --wheel"],
        "task_dep": ["i18n_compile"],
        "file_dep": [str(path) for path in BUILD_DEPS],
        "targets": [WHEEL_TARGET],
        "clean": True,
        "verbosity": 2,
    }


def task_sdist():
    return {
        "actions": [f"{PYTHON} -m build --sdist"],
        "file_dep": [str(path) for path in BUILD_DEPS],
        "targets": [f"dist/nexus_sync-{PACKAGE_VERSION}.tar.gz"],
        "clean": True,
        "verbosity": 2,
    }


def task_package():
    return {
        "actions": None,
        "task_dep": ["wheel", "sdist"],
        "verbosity": 2,
    }


def task_pyinstaller_cli():
    return {
        "actions": [
            f"{PYTHON} -m PyInstaller --onefile src/nexus_sync/cli/__main__.py "
            f'--name nexus-cli --add-data "{LOCALE_DATA}"'
        ],
        "task_dep": ["i18n_compile"],
        "file_dep": [str(path) for path in [*BUILD_DEPS, *MO_FILES]],
        "clean": True,
        "verbosity": 2,
    }


def task_pyinstaller_client():
    return {
        "actions": [
            f"{PYTHON} -m PyInstaller --onefile src/nexus_sync/client/__main__.py --name nexus-sync-client"
        ],
        "file_dep": [str(path) for path in BUILD_DEPS],
        "clean": True,
        "verbosity": 2,
    }


def task_pyinstaller_server():
    return {
        "actions": [
            f"{PYTHON} -m PyInstaller --onefile src/nexus_sync/server/__main__.py --name nexus-sync-server"
        ],
        "file_dep": [str(path) for path in BUILD_DEPS],
        "clean": True,
        "verbosity": 2,
    }


def task_pyinstaller():
    return {
        "actions": None,
        "task_dep": ["pyinstaller_client", "pyinstaller_server", "pyinstaller_cli"],
        "verbosity": 2,
    }


def task_clean_dist():
    return {
        "actions": ["rm -rf dist build src/*.egg-info *.spec"],
        "verbosity": 2,
    }
