import importlib.util
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_dodo() -> Any:
    spec = importlib.util.spec_from_file_location("dodo", PROJECT_ROOT / "dodo.py")
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _actions(task: dict[str, Any]) -> list[str]:
    return [str(action) for action in task["actions"]]


def test_doit_has_wheel_task() -> None:
    dodo = _load_dodo()

    task = dodo.task_wheel()

    assert task["verbosity"] == 2
    assert "dist/nexus_sync-0.1.0-py3-none-any.whl" in task["targets"]
    assert "pyproject.toml" in task["file_dep"]
    assert any("python -m build --wheel" in action for action in _actions(task))


def test_doit_has_clean_dist_task() -> None:
    dodo = _load_dodo()

    task = dodo.task_clean_dist()

    assert any("dist" in action for action in _actions(task))
    assert any("build" in action for action in _actions(task))
    assert any("*.egg-info" in action for action in _actions(task))


def test_doit_default_tasks_include_checks_and_wheel() -> None:
    dodo = _load_dodo()

    assert dodo.DOIT_CONFIG["default_tasks"] == ["test", "typecheck", "format_check", "wheel"]


def test_doit_has_i18n_compile_task() -> None:
    dodo = _load_dodo()

    task = dodo.task_i18n_compile()

    assert any("compile" in action for action in _actions(task))
    assert any(target.endswith("nexus.mo") for target in task["targets"])


def test_doit_has_docs_task() -> None:
    dodo = _load_dodo()

    task = dodo.task_docs()

    assert any("sphinx" in action and "-W" in action for action in _actions(task))
    assert "docs/conf.py" in task["file_dep"]


def test_pyinstaller_cli_bundles_locale_catalogs() -> None:
    dodo = _load_dodo()

    task = dodo.task_pyinstaller_cli()

    assert "i18n_compile" in task["task_dep"]
    assert any("--add-data" in action and "locale" in action for action in _actions(task))
