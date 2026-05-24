from datetime import UTC, datetime

from fastapi.testclient import TestClient

from nexus_sync.common import Command, CommandKind, CommandResultStatus, CommandStatus
from nexus_sync.server import (
    DEFAULT_COMMAND_POLL_SECONDS,
    DEFAULT_IDLE_POLL_SECONDS,
    Store,
    InMemoryStore,
    create_app,
)


def _heartbeat_payload(client_id: str = "macbook-pro-01", result: dict | None = None) -> dict:
    return {
        "client_id": client_id,
        "observed_at": "2026-05-24T13:20:30Z",
        "client": {
            "hostname": "macbook-pro.local",
            "platform": "darwin",
            "version": "0.1.0",
        },
        "state": {
            "local_time": "2026-05-24T16:20:30+03:00",
            "uptime_seconds": 1200,
        },
        "last_command_result": result,
    }


def _client(store: Store | None = None) -> TestClient:
    app = create_app(
        store=store or InMemoryStore(),
        client_tokens={"macbook-pro-01": "client-token", "other-client": "other-token"},
    )
    return TestClient(app)


def test_heartbeat_requires_bearer_token() -> None:
    client = _client()

    response = client.post("/api/v1/client/heartbeat", json=_heartbeat_payload())

    assert response.status_code == 401


def test_heartbeat_rejects_token_for_another_client() -> None:
    client = _client()

    response = client.post(
        "/api/v1/client/heartbeat",
        json=_heartbeat_payload(),
        headers={"Authorization": "Bearer other-token"},
    )

    assert response.status_code == 403


def test_heartbeat_returns_bad_request_for_invalid_payload() -> None:
    payload = _heartbeat_payload()
    payload["unexpected"] = True
    client = _client()

    response = client.post(
        "/api/v1/client/heartbeat",
        json=payload,
        headers={"Authorization": "Bearer client-token"},
    )

    assert response.status_code == 400


def test_heartbeat_accepts_state_without_command() -> None:
    store = InMemoryStore()
    client = _client(store)

    response = client.post(
        "/api/v1/client/heartbeat",
        json=_heartbeat_payload(),
        headers={"Authorization": "Bearer client-token"},
    )

    assert response.status_code == 200
    assert response.json()["command"] is None
    assert response.json()["next_poll_after_seconds"] == DEFAULT_IDLE_POLL_SECONDS
    assert store.clients["macbook-pro-01"].hostname == "macbook-pro.local"


def test_heartbeat_delivers_pending_command_and_marks_it_delivered() -> None:
    store = InMemoryStore()
    store.enqueue_command(
        Command(
            id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
            kind=CommandKind.EXEC,
            name="hostname",
            args={},
            timeout_seconds=30,
        ),
        client_id="macbook-pro-01",
        now=datetime(2026, 5, 24, 13, 20, 0, tzinfo=UTC),
    )
    client = _client(store)

    response = client.post(
        "/api/v1/client/heartbeat",
        json=_heartbeat_payload(),
        headers={"Authorization": "Bearer client-token"},
    )

    body = response.json()
    assert response.status_code == 200
    assert body["next_poll_after_seconds"] == DEFAULT_COMMAND_POLL_SECONDS
    assert body["command"]["id"] == "cmd_01JY3H8V8W8P3FXDR3S2BM7M6B"
    assert store.commands["cmd_01JY3H8V8W8P3FXDR3S2BM7M6B"].status == CommandStatus.DELIVERED
    assert store.commands["cmd_01JY3H8V8W8P3FXDR3S2BM7M6B"].attempts == 1


def test_heartbeat_records_command_result() -> None:
    store = InMemoryStore()
    store.enqueue_command(
        Command(
            id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
            kind=CommandKind.EXEC,
            name="hostname",
            args={},
            timeout_seconds=30,
        ),
        client_id="macbook-pro-01",
        now=datetime(2026, 5, 24, 13, 20, 0, tzinfo=UTC),
    )
    store.take_next_command("macbook-pro-01", datetime(2026, 5, 24, 13, 20, 1, tzinfo=UTC))
    client = _client(store)

    response = client.post(
        "/api/v1/client/heartbeat",
        json=_heartbeat_payload(
            result={
                "command_id": "cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
                "status": "succeeded",
                "started_at": "2026-05-24T13:20:02Z",
                "finished_at": "2026-05-24T13:20:03Z",
                "return_code": 0,
                "stdout": "host\n",
                "stderr": "",
            }
        ),
        headers={"Authorization": "Bearer client-token"},
    )

    assert response.status_code == 200
    assert store.commands["cmd_01JY3H8V8W8P3FXDR3S2BM7M6B"].status == CommandStatus.SUCCEEDED
    assert len(store.results) == 1
    assert store.results[0].status == CommandResultStatus.SUCCEEDED


def test_heartbeat_rejects_unknown_command_result() -> None:
    client = _client()

    response = client.post(
        "/api/v1/client/heartbeat",
        json=_heartbeat_payload(
            result={
                "command_id": "cmd_unknown",
                "status": "succeeded",
                "return_code": 0,
                "stdout": "",
                "stderr": "",
            }
        ),
        headers={"Authorization": "Bearer client-token"},
    )

    assert response.status_code == 409
