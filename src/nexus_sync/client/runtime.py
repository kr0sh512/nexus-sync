import json
import logging
import os
import platform
import shlex
import socket
import urllib.error
import urllib.request
from collections.abc import Mapping as MappingABC
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from types import TracebackType
from typing import Callable, Mapping, Protocol, Self

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from nexus_sync.client.execute import (
    DEFAULT_PRESET_DESCRIPTIONS,
    DEFAULT_PRESETS,
    CommandAccessPolicy,
    PresetBuilder,
    execute_command,
)
from nexus_sync.common import (
    ClientInfo,
    ClientPlatform,
    ClientState,
    ClientCommandCapability,
    CommandResult,
    HeartbeatRequest,
    HeartbeatResponse,
)

CLIENT_VERSION = "0.1.0"
HEARTBEAT_PATH = "/api/v1/client/heartbeat"
logger = logging.getLogger(__name__)


class ClientConfigError(ValueError):
    pass


class HeartbeatError(RuntimeError):
    pass


class HeartbeatHTTPResponse(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def read(self) -> bytes: ...


HeartbeatOpener = Callable[[urllib.request.Request], HeartbeatHTTPResponse]


@dataclass(frozen=True)
class ClientConfig:
    server_url: str
    client_id: str
    token: str
    command_access_policy: CommandAccessPolicy
    command_presets: Mapping[str, PresetBuilder] = field(default_factory=lambda: DEFAULT_PRESETS)
    command_descriptions: Mapping[str, str] = field(
        default_factory=lambda: DEFAULT_PRESET_DESCRIPTIONS
    )
    logging_level: str = "INFO"


def find_client_config_path(
    *,
    env: Mapping[str, str] = os.environ,
    cwd: Path | None = None,
    home: Path | None = None,
) -> Path | None:
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    candidates = [
        cwd / "nexus.yml",
        cwd / "nexus.yaml",
    ]

    xdg_config_home = env.get("XDG_CONFIG_HOME")
    if xdg_config_home and xdg_config_home.strip():
        xdg_dir = Path(xdg_config_home).expanduser()
        candidates.extend([xdg_dir / "nexus.yml", xdg_dir / "nexus.yaml"])

    candidates.extend(
        [
            home / ".config" / "nexus.yml",
            home / ".config" / "nexus.yaml",
            home / ".config" / "nexus" / "config.yml",
            home / ".config" / "nexus" / "config.yaml",
        ]
    )

    return next((path for path in candidates if path.is_file()), None)


def load_client_config(
    env: Mapping[str, str] = os.environ,
    *,
    config_path: Path | str | None = None,
) -> ClientConfig:
    path = Path(config_path) if config_path is not None else find_client_config_path(env=env)
    if path is None:
        raise ClientConfigError("client config file not found")

    try:
        raw_config = yaml.safe_load(path.read_text())
    except OSError as error:
        raise ClientConfigError(f"failed to read client config file {path}: {error}") from error
    except yaml.YAMLError as error:
        raise ClientConfigError(f"failed to parse client config file {path}: {error}") from error

    if not isinstance(raw_config, MappingABC):
        raise ClientConfigError("client config file must contain a YAML mapping")

    server_url = _required_config_string(raw_config, "server_url").rstrip("/")
    client_id = _required_config_string(raw_config, "client_id")
    token = _required_config_string(raw_config, "client_token")
    commands = _load_configured_commands(raw_config.get("allowed_commands", []))

    return ClientConfig(
        server_url=server_url,
        client_id=client_id,
        token=token,
        command_access_policy=CommandAccessPolicy.allow(commands.presets),
        command_presets=commands.presets,
        command_descriptions=commands.descriptions,
        logging_level=str(raw_config.get("logging_level", "INFO")).strip() or "INFO",
    )


def build_heartbeat_request(
    config: ClientConfig,
    *,
    last_command_result: CommandResult | None = None,
) -> HeartbeatRequest:
    now = datetime.now(UTC)
    return HeartbeatRequest(
        client_id=config.client_id,
        observed_at=now,
        client=ClientInfo(
            hostname=socket.gethostname(),
            platform=_current_platform(),
            version=CLIENT_VERSION,
        ),
        state=ClientState(
            local_time=datetime.now().astimezone(),
            uptime_seconds=None,
        ),
        available_commands=list_available_commands(
            config.command_access_policy,
            presets=config.command_presets,
            descriptions=config.command_descriptions,
        ),
        last_command_result=last_command_result,
    )


def list_available_commands(
    access_policy: CommandAccessPolicy,
    *,
    presets: Mapping[str, PresetBuilder] = DEFAULT_PRESETS,
    descriptions: Mapping[str, str] = DEFAULT_PRESET_DESCRIPTIONS,
) -> list[ClientCommandCapability]:
    return [
        ClientCommandCapability(
            name=name,
            description=descriptions.get(name, ""),
        )
        for name in sorted(presets)
        if access_policy.allows(name)
    ]


def send_heartbeat(
    config: ClientConfig,
    heartbeat: HeartbeatRequest,
    *,
    opener: HeartbeatOpener = urllib.request.urlopen,
) -> HeartbeatResponse:
    payload = heartbeat.model_dump_json().encode()
    request = urllib.request.Request(
        f"{config.server_url}{HEARTBEAT_PATH}",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.token}",
        },
        method="POST",
    )

    try:
        with opener(request) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise HeartbeatError(f"heartbeat failed with HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise HeartbeatError(f"heartbeat request failed: {error.reason}") from error
    except OSError as error:
        raise HeartbeatError(f"heartbeat request failed: {error}") from error

    try:
        return HeartbeatResponse.model_validate_json(body)
    except ValidationError as error:
        raise HeartbeatError(f"heartbeat response is invalid: {error}") from error


def run_once(
    config: ClientConfig,
    *,
    last_command_result: CommandResult | None = None,
    heartbeat_sender: Callable[
        [ClientConfig, HeartbeatRequest],
        HeartbeatResponse,
    ] = send_heartbeat,
    executor: Callable[..., CommandResult] = execute_command,
) -> CommandResult | None:
    response = heartbeat_sender(
        config,
        build_heartbeat_request(config, last_command_result=last_command_result),
    )
    if response.command is None:
        return None

    return executor(
        response.command,
        access_policy=config.command_access_policy,
        presets=config.command_presets,
    )


def main(argv: list[str] | None = None) -> int:
    _ = argv
    try:
        config = load_client_config()
        result = run_once(config)
    except (ClientConfigError, HeartbeatError, ValueError) as error:
        logger.error("nexus-sync client error: %s", error)
        return 1

    if result is None:
        logger.info("heartbeat accepted; no command")
        return 0

    logger.info(
        "command result: %s",
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
    )
    return 0


@dataclass(frozen=True)
class _ConfiguredCommands:
    presets: dict[str, PresetBuilder]
    descriptions: dict[str, str]


def _load_configured_commands(raw_commands: object) -> _ConfiguredCommands:
    if raw_commands is None:
        raw_commands = []
    if not isinstance(raw_commands, list):
        raise ClientConfigError("allowed_commands must be a list")

    presets: dict[str, PresetBuilder] = {}
    descriptions: dict[str, str] = {}
    for index, raw_command in enumerate(raw_commands):
        if not isinstance(raw_command, MappingABC):
            raise ClientConfigError(f"allowed_commands[{index}] must be a mapping")
        name = _required_config_string(raw_command, "name", prefix=f"allowed_commands[{index}]")
        description = _required_config_string(
            raw_command,
            "description",
            prefix=f"allowed_commands[{index}]",
        )
        command_line = _required_config_string(
            raw_command, "cmd", prefix=f"allowed_commands[{index}]"
        )
        argv = shlex.split(command_line, posix=os.name != "nt")
        if not argv:
            raise ClientConfigError(f"allowed_commands[{index}].cmd must not be empty")
        if name in presets:
            raise ClientConfigError(f"duplicate allowed command name: {name}")
        presets[name] = _static_preset(argv)
        descriptions[name] = description

    return _ConfiguredCommands(presets=presets, descriptions=descriptions)


def _static_preset(argv: list[str]) -> PresetBuilder:
    def build(args: Mapping[str, object]) -> list[str]:
        if args:
            raise ValueError("configured commands do not accept arguments")
        return list(argv)

    return build


def _required_config_string(
    config: MappingABC[object, object],
    name: str,
    *,
    prefix: str | None = None,
) -> str:
    value = config.get(name)
    display_name = f"{prefix}.{name}" if prefix else name
    if not isinstance(value, str) or not value.strip():
        raise ClientConfigError(f"{display_name} is required")
    return value.strip()


def _current_platform() -> ClientPlatform:
    system = platform.system().lower()
    if system == "linux":
        return ClientPlatform.LINUX
    if system == "darwin":
        return ClientPlatform.DARWIN
    if system == "windows":
        return ClientPlatform.WINDOWS
    return ClientPlatform.UNKNOWN
