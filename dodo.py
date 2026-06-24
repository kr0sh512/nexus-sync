import sys
from pathlib import Path

DOIT_CONFIG = {
    "default_tasks": ["test", "typecheck", "format_check", "wheel"],
}

PYTHON = sys.executable
PACKAGE_VERSION = "0.1.0"
WHEEL_TARGET = f"dist/nexus_sync-{PACKAGE_VERSION}-py3-none-any.whl"
SRC_FILES = list(Path("src").rglob("*.py"))
TEST_FILES = list(Path("tests").rglob("*.py"))
DOC_FILES = [Path("README.md"), *Path("docs").glob("*.md")]
BUILD_DEPS = [Path("pyproject.toml"), Path("README.md"), *SRC_FILES]


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


def task_wheel():
    return {
        "actions": [f"{PYTHON} -m build --wheel"],
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
            f"{PYTHON} -m PyInstaller --onefile src/nexus_sync/cli/__main__.py --name nexus-cli"
        ],
        "file_dep": [str(path) for path in BUILD_DEPS],
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
