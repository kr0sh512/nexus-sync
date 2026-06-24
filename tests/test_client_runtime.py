import io
import urllib.error
import urllib.request
from datetime import UTC, datetime

import pytest

from nexus_sync.client.execute import CommandAccessPolicy
from nexus_sync.client.runtime import (
    CLIENT_ID_ENV,
    CLIENT_TOKEN_ENV,
    SERVER_URL_ENV,
    ClientConfig,
    ClientConfigError,
    HeartbeatError,
    build_heartbeat_request,
    list_available_commands,
    load_client_config,
    main,
    run_once,
    send_heartbeat,
)
from nexus_sync.common import (
    Command,
    CommandKind,
    CommandResult,
    CommandResultStatus,
    HeartbeatRequest,
    HeartbeatResponse,
)


def _config(policy: CommandAccessPolicy | None = None) -> ClientConfig:
    return ClientConfig(
        server_url="https://nexus.example.test",
        client_id="macbook-pro-01",
        token="client-token",
        command_access_policy=policy or CommandAccessPolicy.deny_all(),
    )


def test_load_client_config_reads_required_env_and_normalizes_server_url() -> None:
    config = load_client_config(
        {
            SERVER_URL_ENV: "https://nexus.example.test/",
            CLIENT_ID_ENV: "macbook-pro-01",
            CLIENT_TOKEN_ENV: "client-token",
            "NEXUS_SYNC_ALLOWED_COMMANDS": "hostname",
        }
    )

    assert config.server_url == "https://nexus.example.test"
    assert config.client_id == "macbook-pro-01"
    assert config.token == "client-token"
    assert config.command_access_policy.allows("hostname")
    assert not config.command_access_policy.allows("network_interfaces")


@pytest.mark.parametrize("missing_name", [SERVER_URL_ENV, CLIENT_ID_ENV, CLIENT_TOKEN_ENV])
def test_load_client_config_requires_env_values(missing_name: str) -> None:
    env = {
        SERVER_URL_ENV: "https://nexus.example.test",
        CLIENT_ID_ENV: "macbook-pro-01",
        CLIENT_TOKEN_ENV: "client-token",
    }
    del env[missing_name]

    with pytest.raises(ClientConfigError, match=missing_name):
        load_client_config(env)


def test_build_heartbeat_request_contains_client_state(monkeypatch) -> None:
    monkeypatch.setattr("socket.gethostname", lambda: "macbook-pro.local")
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    heartbeat = build_heartbeat_request(_config())
    serialized = heartbeat.model_dump(mode="json")

    assert heartbeat.client_id == "macbook-pro-01"
    assert heartbeat.client.hostname == "macbook-pro.local"
    assert heartbeat.client.platform == "darwin"
    assert heartbeat.client.version == "0.1.0"
    assert heartbeat.last_command_result is None
    assert serialized["client_id"] == "macbook-pro-01"
    assert serialized["state"]["uptime_seconds"] is None


def test_list_available_commands_returns_allowed_command_names_and_descriptions() -> None:
    commands = list_available_commands(CommandAccessPolicy.allow(["hostname"]))

    assert [command.model_dump() for command in commands] == [
        {"name": "hostname", "description": "Return system hostname"}
    ]


def test_build_heartbeat_request_includes_available_commands(monkeypatch) -> None:
    monkeypatch.setattr("socket.gethostname", lambda: "macbook-pro.local")
    monkeypatch.setattr("platform.system", lambda: "Darwin")

    heartbeat = build_heartbeat_request(_config(CommandAccessPolicy.allow(["hostname"])))

    assert [command.name for command in heartbeat.available_commands] == ["hostname"]
    assert heartbeat.available_commands[0].description == "Return system hostname"


def test_build_heartbeat_request_includes_last_command_result(monkeypatch) -> None:
    monkeypatch.setattr("socket.gethostname", lambda: "macbook-pro.local")
    monkeypatch.setattr("platform.system", lambda: "Darwin")
    command_result = CommandResult(
        command_id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
        status=CommandResultStatus.SUCCEEDED,
        started_at=datetime(2026, 5, 24, 13, 20, 31, tzinfo=UTC),
        finished_at=datetime(2026, 5, 24, 13, 20, 32, tzinfo=UTC),
        return_code=0,
        stdout="host\n",
        stderr="",
    )

    heartbeat = build_heartbeat_request(_config(), last_command_result=command_result)
    serialized = heartbeat.model_dump(mode="json")

    assert heartbeat.last_command_result == command_result
    assert serialized["last_command_result"]["command_id"] == command_result.command_id
    assert serialized["last_command_result"]["status"] == "succeeded"
    assert serialized["last_command_result"]["return_code"] == 0
    assert serialized["last_command_result"]["stdout"] == "host\n"


def test_send_heartbeat_posts_json_with_bearer_token() -> None:
    captured = {}

    def fake_opener(request: urllib.request.Request):
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["content_type"] = request.get_header("Content-type")
        captured["data"] = request.data
        return _Response(
            HeartbeatResponse(
                server_time=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
                next_poll_after_seconds=60,
                command=None,
            )
            .model_dump_json()
            .encode()
        )

    response = send_heartbeat(
        _config(),
        HeartbeatRequest(
            client_id="macbook-pro-01",
            observed_at=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
            client={
                "hostname": "macbook-pro.local",
                "platform": "darwin",
                "version": "0.1.0",
            },
            state={
                "local_time": datetime(2026, 5, 24, 16, 20, 30, tzinfo=UTC),
                "uptime_seconds": None,
            },
            last_command_result=None,
        ),
        opener=fake_opener,
    )

    assert response.command is None
    assert captured["url"] == "https://nexus.example.test/api/v1/client/heartbeat"
    assert captured["authorization"] == "Bearer client-token"
    assert captured["content_type"] == "application/json"
    assert b"macbook-pro-01" in captured["data"]


def test_send_heartbeat_serializes_last_command_result() -> None:
    captured = {}

    def fake_opener(request: urllib.request.Request):
        captured["data"] = request.data
        return _Response(
            HeartbeatResponse(
                server_time=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
                next_poll_after_seconds=60,
                command=None,
            )
            .model_dump_json()
            .encode()
        )

    heartbeat = HeartbeatRequest(
        client_id="macbook-pro-01",
        observed_at=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
        client={
            "hostname": "macbook-pro.local",
            "platform": "darwin",
            "version": "0.1.0",
        },
        state={
            "local_time": datetime(2026, 5, 24, 16, 20, 30, tzinfo=UTC),
            "uptime_seconds": None,
        },
        last_command_result={
            "command_id": "cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
            "status": "succeeded",
            "started_at": "2026-05-24T13:20:31Z",
            "finished_at": "2026-05-24T13:20:32Z",
            "return_code": 0,
            "stdout": "host\n",
            "stderr": "",
        },
    )

    send_heartbeat(_config(), heartbeat, opener=fake_opener)

    assert b'"last_command_result":' in captured["data"]
    assert b'"command_id":"cmd_01JY3H8V8W8P3FXDR3S2BM7M6B"' in captured["data"]
    assert b'"stdout":"host\\n"' in captured["data"]


def test_send_heartbeat_maps_http_error_to_runtime_error() -> None:
    def fake_opener(_request: urllib.request.Request):
        raise urllib.error.HTTPError(
            url="https://nexus.example.test/api/v1/client/heartbeat",
            code=401,
            msg="Unauthorized",
            hdrs={},
            fp=io.BytesIO(b'{"detail":"invalid bearer token"}'),
        )

    with pytest.raises(HeartbeatError, match="HTTP 401"):
        send_heartbeat(_config(), build_heartbeat_request(_config()), opener=fake_opener)


def test_run_once_without_command_does_not_call_executor() -> None:
    executor_called = False

    def fake_sender(_config: ClientConfig, _heartbeat: HeartbeatRequest) -> HeartbeatResponse:
        return HeartbeatResponse(
            server_time=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
            next_poll_after_seconds=60,
            command=None,
        )

    def fake_executor(*_args, **_kwargs):
        nonlocal executor_called
        executor_called = True
        raise AssertionError("executor should not be called")

    result = run_once(_config(), heartbeat_sender=fake_sender, executor=fake_executor)

    assert result is None
    assert executor_called is False


def test_run_once_executes_command_with_configured_access_policy() -> None:
    policy = CommandAccessPolicy.allow(["hostname"])
    seen = {}

    def fake_sender(_config: ClientConfig, _heartbeat: HeartbeatRequest) -> HeartbeatResponse:
        return HeartbeatResponse(
            server_time=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
            next_poll_after_seconds=10,
            command=Command(
                id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
                kind=CommandKind.EXEC,
                name="hostname",
                args={},
                timeout_seconds=30,
            ),
        )

    def fake_executor(command: Command, **kwargs) -> CommandResult:
        seen["command"] = command
        seen["access_policy"] = kwargs["access_policy"]
        return CommandResult(
            command_id=command.id,
            status=CommandResultStatus.SUCCEEDED,
            return_code=0,
            stdout="host\n",
        )

    result = run_once(_config(policy), heartbeat_sender=fake_sender, executor=fake_executor)

    assert result is not None
    assert result.status == CommandResultStatus.SUCCEEDED
    assert seen["command"].name == "hostname"
    assert seen["access_policy"] == policy


def test_run_once_sends_previous_command_result() -> None:
    previous_result = CommandResult(
        command_id="cmd_previous",
        status=CommandResultStatus.FAILED,
        return_code=1,
        stdout="",
        stderr="failed\n",
    )
    seen = {}

    def fake_sender(_config: ClientConfig, heartbeat: HeartbeatRequest) -> HeartbeatResponse:
        seen["last_command_result"] = heartbeat.last_command_result
        return HeartbeatResponse(
            server_time=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
            next_poll_after_seconds=60,
            command=None,
        )

    result = run_once(
        _config(),
        last_command_result=previous_result,
        heartbeat_sender=fake_sender,
    )

    assert result is None
    assert seen["last_command_result"] == previous_result


def test_main_returns_non_zero_for_missing_config(monkeypatch, caplog) -> None:
    monkeypatch.delenv(SERVER_URL_ENV, raising=False)
    monkeypatch.delenv(CLIENT_ID_ENV, raising=False)
    monkeypatch.delenv(CLIENT_TOKEN_ENV, raising=False)

    exit_code = main([])

    assert exit_code == 1
    assert SERVER_URL_ENV in caplog.text


def test_main_logs_success_without_command(monkeypatch, caplog) -> None:
    caplog.set_level("INFO")
    monkeypatch.setenv(SERVER_URL_ENV, "https://nexus.example.test")
    monkeypatch.setenv(CLIENT_ID_ENV, "macbook-pro-01")
    monkeypatch.setenv(CLIENT_TOKEN_ENV, "client-token")
    monkeypatch.setattr("nexus_sync.client.runtime.run_once", lambda _config: None)

    exit_code = main([])

    assert exit_code == 0
    assert "heartbeat accepted; no command" in caplog.text


def test_main_logs_command_result(monkeypatch, caplog) -> None:
    caplog.set_level("INFO")
    monkeypatch.setenv(SERVER_URL_ENV, "https://nexus.example.test")
    monkeypatch.setenv(CLIENT_ID_ENV, "macbook-pro-01")
    monkeypatch.setenv(CLIENT_TOKEN_ENV, "client-token")
    monkeypatch.setattr(
        "nexus_sync.client.runtime.run_once",
        lambda _config: CommandResult(
            command_id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
            status=CommandResultStatus.SUCCEEDED,
            return_code=0,
            stdout="host\n",
            stderr="",
        ),
    )

    exit_code = main([])

    assert exit_code == 0
    assert "command result:" in caplog.text
    assert '"command_id":"cmd_01JY3H8V8W8P3FXDR3S2BM7M6B"' in caplog.text


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._body
