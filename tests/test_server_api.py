from fastapi.testclient import TestClient

from nexus_sync.server import InMemoryStore, Store, create_app


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


def _send_heartbeat(client: TestClient, payload: dict | None = None):
    return client.post(
        "/api/v1/client/heartbeat",
        json=payload or _heartbeat_payload(),
        headers={"Authorization": "Bearer client-token"},
    )


def test_server_lists_clients_after_heartbeat() -> None:
    store = InMemoryStore()
    client = _client(store)
    payload = _heartbeat_payload()
    payload["available_commands"] = [
        {"name": "hostname", "description": "Get hostname"},
    ]
    _send_heartbeat(client, payload)

    response = client.get("/api/v1/server/clients")

    assert response.status_code == 200
    assert response.json()["clients"][0]["id"] == "macbook-pro-01"
    assert response.json()["clients"][0]["available_commands"] == [
        {"name": "hostname", "description": "Get hostname"},
    ]


def test_server_queues_command_for_client_and_heartbeat_delivers_it() -> None:
    store = InMemoryStore()
    client = _client(store)
    _send_heartbeat(client)

    created = client.post(
        "/api/v1/server/clients/macbook-pro-01/commands",
        json={"name": "hostname", "args": {}, "timeout_seconds": 30},
    )

    assert created.status_code == 201
    command_id = created.json()["id"]
    assert created.json()["client_id"] == "macbook-pro-01"
    assert created.json()["status"] == "pending"

    heartbeat = _send_heartbeat(client)

    assert heartbeat.status_code == 200
    assert heartbeat.json()["command"]["id"] == command_id
    assert heartbeat.json()["command"]["name"] == "hostname"


def test_server_rejects_command_for_unknown_client() -> None:
    client = _client()

    response = client.post(
        "/api/v1/server/clients/missing-client/commands",
        json={"name": "hostname", "args": {}, "timeout_seconds": 30},
    )

    assert response.status_code == 404


def test_server_returns_command_with_result_after_client_reports_result() -> None:
    store = InMemoryStore()
    client = _client(store)
    _send_heartbeat(client)
    created = client.post(
        "/api/v1/server/clients/macbook-pro-01/commands",
        json={"name": "hostname", "args": {}, "timeout_seconds": 30},
    )
    command_id = created.json()["id"]
    _send_heartbeat(client)

    reported = _send_heartbeat(
        client,
        _heartbeat_payload(
            result={
                "command_id": command_id,
                "status": "succeeded",
                "return_code": 0,
                "stdout": "host\n",
                "stderr": "",
            }
        ),
    )
    fetched = client.get(f"/api/v1/server/commands/{command_id}")

    assert reported.status_code == 200
    assert fetched.status_code == 200
    assert fetched.json()["status"] == "succeeded"
    assert fetched.json()["result"]["stdout"] == "host\n"
