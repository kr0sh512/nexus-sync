import json
import os
import platform
import socket
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Mapping

from pydantic import ValidationError

from nexus_sync.client.config import load_command_access_policy
from nexus_sync.client.execute import CommandAccessPolicy, execute_command
from nexus_sync.common import (
    ClientInfo,
    ClientPlatform,
    ClientState,
    CommandResult,
    HeartbeatRequest,
    HeartbeatResponse,
)

SERVER_URL_ENV = "NEXUS_SYNC_SERVER_URL"
CLIENT_ID_ENV = "NEXUS_SYNC_CLIENT_ID"
CLIENT_TOKEN_ENV = "NEXUS_SYNC_CLIENT_TOKEN"
CLIENT_VERSION = "0.1.0"
HEARTBEAT_PATH = "/api/v1/client/heartbeat"


class ClientConfigError(ValueError):
    pass


class HeartbeatError(RuntimeError):
    pass


@dataclass(frozen=True)
class ClientConfig:
    server_url: str
    client_id: str
    token: str
    command_access_policy: CommandAccessPolicy


def load_client_config(env: Mapping[str, str] = os.environ) -> ClientConfig:
    server_url = _required_env(env, SERVER_URL_ENV).rstrip("/")
    client_id = _required_env(env, CLIENT_ID_ENV)
    token = _required_env(env, CLIENT_TOKEN_ENV)
    return ClientConfig(
        server_url=server_url,
        client_id=client_id,
        token=token,
        command_access_policy=load_command_access_policy(env),
    )


def build_heartbeat_request(config: ClientConfig) -> HeartbeatRequest:
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
        last_command_result=None,
    )


def send_heartbeat(
    config: ClientConfig,
    heartbeat: HeartbeatRequest,
    *,
    opener: Callable[[urllib.request.Request], object] = urllib.request.urlopen,
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
    heartbeat_sender: Callable[
        [ClientConfig, HeartbeatRequest],
        HeartbeatResponse,
    ] = send_heartbeat,
    executor: Callable[..., CommandResult] = execute_command,
) -> CommandResult | None:
    response = heartbeat_sender(config, build_heartbeat_request(config))
    if response.command is None:
        return None

    return executor(
        response.command,
        access_policy=config.command_access_policy,
    )


def main(argv: list[str] | None = None) -> int:
    _ = argv
    try:
        config = load_client_config()
        result = run_once(config)
    except (ClientConfigError, HeartbeatError, ValueError) as error:
        print(f"nexus-sync client error: {error}", file=sys.stderr)
        return 1

    if result is None:
        print("heartbeat accepted; no command")
        return 0

    print(
        json.dumps(
            result.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


def _required_env(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or not value.strip():
        raise ClientConfigError(f"{name} is required")
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
