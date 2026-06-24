import io
import json
import urllib.request
from typing import Any

import pytest

from nexus_sync.cli.__main__ import (
    DEFAULT_SERVER_URL,
    format_client,
    format_clients,
    format_command,
    main,
    request_json,
)


class _Response:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def test_request_json_sends_get_request() -> None:
    captured: dict[str, Any] = {}

    def fake_opener(request: urllib.request.Request) -> _Response:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["data"] = request.data
        return _Response({"clients": []})

    result = request_json("GET", "http://server.test/api/v1/server/clients", opener=fake_opener)

    assert result == {"clients": []}
    assert captured == {
        "url": "http://server.test/api/v1/server/clients",
        "method": "GET",
        "data": None,
    }


def test_request_json_sends_post_json_request() -> None:
    captured: dict[str, Any] = {}

    def fake_opener(request: urllib.request.Request) -> _Response:
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["content_type"] = request.get_header("Content-type")
        captured["payload"] = json.loads((request.data or b"").decode())
        return _Response({"id": "cmd_123", "status": "pending"})

    result = request_json(
        "POST",
        "http://server.test/api/v1/server/clients/linux-client/commands",
        payload={"name": "hostname", "args": {}, "timeout_seconds": 30},
        opener=fake_opener,
    )

    assert result == {"id": "cmd_123", "status": "pending"}
    assert captured == {
        "url": "http://server.test/api/v1/server/clients/linux-client/commands",
        "method": "POST",
        "content_type": "application/json",
        "payload": {"name": "hostname", "args": {}, "timeout_seconds": 30},
    }


def test_main_lists_clients_as_text(capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_request(
        method: str, url: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        calls.append((method, url, payload))
        return {
            "clients": [
                {
                    "id": "linux-client",
                    "hostname": "box",
                    "platform": "linux",
                    "version": "0.1.0",
                    "last_seen_at": "2026-06-24T12:00:00Z",
                    "available_commands": [{"name": "hostname", "description": "Return hostname"}],
                }
            ]
        }

    exit_code = main(["--server-url", "http://server.test", "--list"], requester=fake_request)

    assert exit_code == 0
    assert calls == [("GET", "http://server.test/api/v1/server/clients", None)]
    output = capsys.readouterr().out
    assert "clients:" in output
    assert "linux-client" in output
    assert "box" in output
    assert "hostname" in output


def test_main_shows_client_as_json(capsys: pytest.CaptureFixture[str]) -> None:
    def fake_request(
        method: str, url: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert method == "GET"
        assert url == f"{DEFAULT_SERVER_URL}/api/v1/server/clients/linux-client"
        assert payload is None
        return {"id": "linux-client", "hostname": "box", "available_commands": []}

    exit_code = main(["--json", "client", "linux-client"], requester=fake_request)

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "id": "linux-client",
        "hostname": "box",
        "available_commands": [],
    }


def test_main_queues_client_command(capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def fake_request(
        method: str, url: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        calls.append((method, url, payload))
        return {
            "id": "cmd_123",
            "client_id": "linux-client",
            "name": "hostname",
            "status": "pending",
            "created_at": "2026-06-24T12:00:00Z",
        }

    exit_code = main(
        [
            "--server-url",
            "http://server.test/",
            "client",
            "linux-client",
            "--run-command",
            "hostname",
            "--timeout-seconds",
            "5",
        ],
        requester=fake_request,
    )

    assert exit_code == 0
    assert calls == [
        (
            "POST",
            "http://server.test/api/v1/server/clients/linux-client/commands",
            {"name": "hostname", "args": {}, "timeout_seconds": 5},
        )
    ]
    output = capsys.readouterr().out
    assert "queued command:" in output
    assert "cmd_123" in output
    assert "pending" in output


def test_main_shows_command_result(capsys: pytest.CaptureFixture[str]) -> None:
    def fake_request(
        method: str, url: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        assert method == "GET"
        assert url == "http://server.test/api/v1/server/commands/cmd_123"
        assert payload is None
        return {
            "id": "cmd_123",
            "client_id": "linux-client",
            "name": "hostname",
            "status": "succeeded",
            "result": {"return_code": 0, "stdout": "box\n", "stderr": ""},
        }

    exit_code = main(["-s", "http://server.test", "command", "cmd_123"], requester=fake_request)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "cmd_123" in output
    assert "succeeded" in output
    assert "stdout:" in output
    assert "box" in output


def test_formatters_include_core_fields() -> None:
    clients_text = format_clients(
        {
            "clients": [
                {
                    "id": "linux-client",
                    "hostname": "box",
                    "platform": "linux",
                    "version": "0.1.0",
                    "last_seen_at": "now",
                    "available_commands": [{"name": "hostname", "description": "Return hostname"}],
                }
            ]
        }
    )
    client_text = format_client(
        {
            "id": "linux-client",
            "hostname": "box",
            "platform": "linux",
            "available_commands": [{"name": "hostname", "description": "Return hostname"}],
        }
    )
    command_text = format_command(
        {
            "id": "cmd_123",
            "client_id": "linux-client",
            "name": "hostname",
            "status": "succeeded",
            "result": {"return_code": 0, "stdout": "box\n", "stderr": ""},
        },
        queued=True,
    )

    assert "linux-client" in clients_text
    assert "hostname" in client_text
    assert "queued command:" in command_text
    assert "box" in command_text
