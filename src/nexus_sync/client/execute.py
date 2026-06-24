import platform
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Mapping, Sequence

from nexus_sync.common import Command, CommandKind, CommandResult, CommandResultStatus

PresetBuilder = Callable[[Mapping[str, Any]], Sequence[str]]

DEFAULT_OUTPUT_LIMIT_BYTES = 64 * 1024
DEFAULT_PRESET_DESCRIPTIONS = {
    "hostname": "Return system hostname",
    "network_interfaces": "Return network interface information",
}


@dataclass(frozen=True)
class CommandAccessPolicy:
    allowed_commands: frozenset[str] = field(default_factory=frozenset)
    full_access: bool = False

    @classmethod
    def allow(cls, command_names: Iterable[str]) -> "CommandAccessPolicy":
        return cls(allowed_commands=frozenset(command_names))

    @classmethod
    def allow_all(cls) -> "CommandAccessPolicy":
        return cls(full_access=True)

    @classmethod
    def deny_all(cls) -> "CommandAccessPolicy":
        return cls()

    def allows(self, command_name: str) -> bool:
        return self.full_access or command_name in self.allowed_commands


def _reject(command: Command, message: str) -> CommandResult:
    now = datetime.now(UTC)
    return CommandResult(
        command_id=command.id,
        status=CommandResultStatus.REJECTED,
        started_at=now,
        finished_at=now,
        stderr=message,
    )


def _network_interfaces(args: Mapping[str, Any]) -> Sequence[str]:
    if args:
        raise ValueError("network_interfaces does not accept arguments")

    system = platform.system().lower()
    if system == "windows":
        return ["ipconfig"]
    if system == "linux":
        return ["ip", "addr"]
    if system == "darwin":
        return ["ifconfig"]
    raise ValueError(f"unsupported platform for network_interfaces: {system or 'unknown'}")


def _hostname(args: Mapping[str, Any]) -> Sequence[str]:
    if args:
        raise ValueError("hostname does not accept arguments")
    return ["hostname"]


DEFAULT_PRESETS: dict[str, PresetBuilder] = {
    "hostname": _hostname,
    "network_interfaces": _network_interfaces,
}
DEFAULT_COMMAND_ACCESS_POLICY = CommandAccessPolicy.allow_all()


def execute_command(
    command: Command,
    *,
    stdin: str | None = None,
    presets: Mapping[str, PresetBuilder] = DEFAULT_PRESETS,
    access_policy: CommandAccessPolicy = DEFAULT_COMMAND_ACCESS_POLICY,
    output_limit_bytes: int = DEFAULT_OUTPUT_LIMIT_BYTES,
) -> CommandResult:
    if command.kind != CommandKind.EXEC:
        return _reject(command, f"unsupported command kind: {command.kind}")

    builder = presets.get(command.name)
    if builder is None:
        return _reject(command, f"unknown command preset: {command.name}")
    if not access_policy.allows(command.name):
        return _reject(command, f"command preset is not allowed: {command.name}")

    try:
        argv = list(builder(command.args))
    except ValueError as error:
        return _reject(command, str(error))

    if not argv:
        return _reject(command, f"command preset returned empty argv: {command.name}")

    started_at = datetime.now(UTC)
    try:
        process = subprocess.run(
            argv,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=command.timeout_seconds,
            shell=False,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        finished_at = datetime.now(UTC)
        return CommandResult(
            command_id=command.id,
            status=CommandResultStatus.TIMED_OUT,
            started_at=started_at,
            finished_at=finished_at,
            stdout=_limit_output(error.stdout or "", output_limit_bytes),
            stderr=_limit_output(error.stderr or "", output_limit_bytes),
        )
    except OSError as error:
        finished_at = datetime.now(UTC)
        return CommandResult(
            command_id=command.id,
            status=CommandResultStatus.FAILED,
            started_at=started_at,
            finished_at=finished_at,
            return_code=None,
            stderr=str(error),
        )

    finished_at = datetime.now(UTC)
    status = (
        CommandResultStatus.SUCCEEDED if process.returncode == 0 else CommandResultStatus.FAILED
    )
    return CommandResult(
        command_id=command.id,
        status=status,
        started_at=started_at,
        finished_at=finished_at,
        return_code=process.returncode,
        stdout=_limit_output(process.stdout, output_limit_bytes),
        stderr=_limit_output(process.stderr, output_limit_bytes),
    )


def _limit_output(value: str | bytes, limit_bytes: int) -> str:
    if isinstance(value, bytes):
        value = value.decode(errors="replace")

    encoded = value.encode()
    if len(encoded) <= limit_bytes:
        return value

    marker = "\n[truncated]"
    marker_bytes = marker.encode()
    if limit_bytes <= len(marker_bytes):
        return encoded[:limit_bytes].decode(errors="ignore")

    content_limit = max(0, limit_bytes - len(marker_bytes))
    truncated = encoded[:content_limit].decode(errors="ignore")
    return f"{truncated}{marker}"
