import subprocess

from nexus_sync.client.execute import execute_command
from nexus_sync.common import Command, CommandKind, CommandResultStatus


def _command(name: str = "hostname", timeout_seconds: int = 30) -> Command:
    return Command(
        id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
        kind=CommandKind.EXEC,
        name=name,
        args={},
        timeout_seconds=timeout_seconds,
    )


def test_execute_command_runs_known_preset_without_shell(monkeypatch) -> None:
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return subprocess.CompletedProcess(argv, 0, stdout="host\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = execute_command(_command())

    assert result.status == CommandResultStatus.SUCCEEDED
    assert result.return_code == 0
    assert result.stdout == "host\n"
    assert calls == [
        (
            ["hostname"],
            {
                "input": None,
                "text": True,
                "capture_output": True,
                "timeout": 30,
                "shell": False,
                "check": False,
            },
        )
    ]


def test_execute_command_rejects_unknown_preset() -> None:
    result = execute_command(_command(name="rm_everything"))

    assert result.status == CommandResultStatus.REJECTED
    assert result.return_code is None
    assert "unknown command preset" in result.stderr


def test_execute_command_maps_non_zero_exit_to_failed(monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 2, stdout="", stderr="failed\n")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = execute_command(_command())

    assert result.status == CommandResultStatus.FAILED
    assert result.return_code == 2
    assert result.stderr == "failed\n"


def test_execute_command_maps_timeout(monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, timeout=kwargs["timeout"], output="partial")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = execute_command(_command(timeout_seconds=1))

    assert result.status == CommandResultStatus.TIMED_OUT
    assert result.return_code is None
    assert result.started_at is not None
    assert result.finished_at is not None


def test_execute_command_truncates_output(monkeypatch) -> None:
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout="abcdefghijklmnopqrstuvwxyz", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = execute_command(_command(), output_limit_bytes=20)

    assert result.stdout.endswith("\n[truncated]")
    assert len(result.stdout.encode()) <= 20


def test_execute_command_rejects_preset_validation_error() -> None:
    command = _command()
    invalid = command.model_copy(update={"args": {"unexpected": True}})

    result = execute_command(invalid)

    assert result.status == CommandResultStatus.REJECTED
    assert "does not accept arguments" in result.stderr
