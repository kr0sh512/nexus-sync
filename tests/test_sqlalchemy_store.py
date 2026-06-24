from datetime import UTC, datetime

from nexus_sync.common import Command, CommandKind, CommandStatus
from nexus_sync.server.sqlalchemy_store import SQLAlchemyStore


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
        "available_commands": [
            {"name": "hostname", "description": "Get hostname"},
        ],
        "last_command_result": result,
    }


def test_sqlalchemy_store_persists_clients_commands_and_results(tmp_path) -> None:
    db_url = f"sqlite:///{tmp_path / 'nexus-sync.db'}"
    store = SQLAlchemyStore(db_url)
    now = datetime(2026, 5, 24, 13, 20, tzinfo=UTC)

    store.upsert_client_from_payload(_heartbeat_payload(), now)
    command = Command(
        id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
        kind=CommandKind.EXEC,
        name="hostname",
        args={},
        timeout_seconds=30,
    )
    store.enqueue_command(command, "macbook-pro-01", now)

    reloaded = SQLAlchemyStore(db_url)
    assert reloaded.get_client("macbook-pro-01") is not None
    assert reloaded.get_client("macbook-pro-01").available_commands[0].name == "hostname"

    delivered = reloaded.take_next_command("macbook-pro-01", now)
    assert delivered is not None
    assert delivered.id == command.id
    assert reloaded.get_command(command.id).status == CommandStatus.DELIVERED

    result_payload = _heartbeat_payload(
        result={
            "command_id": command.id,
            "status": "succeeded",
            "return_code": 0,
            "stdout": "host\n",
            "stderr": "",
        }
    )
    reloaded.record_command_result_from_payload(result_payload, now)

    final = SQLAlchemyStore(db_url)
    assert final.get_command(command.id).status == CommandStatus.SUCCEEDED
    assert final.get_command_result(command.id).stdout == "host\n"
