from datetime import UTC, datetime

from pydantic import ValidationError

from nexus_sync.common import (
    ClientInfo,
    ClientPlatform,
    ClientState,
    Command,
    CommandKind,
    CommandResult,
    CommandResultStatus,
    HeartbeatRequest,
    HeartbeatResponse,
)


def test_heartbeat_request_accepts_payload() -> None:
    payload = HeartbeatRequest(
        client_id="macbook-pro-01",
        observed_at=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
        client=ClientInfo(
            hostname="macbook-pro.local",
            platform=ClientPlatform.DARWIN,
            version="0.1.0",
        ),
        state=ClientState(
            local_time=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
            uptime_seconds=1200,
        ),
        last_command_result=None,
    )

    serialized = payload.model_dump(mode="json")

    assert serialized["client_id"] == "macbook-pro-01"
    assert serialized["client"]["platform"] == "darwin"
    assert serialized["last_command_result"] is None


def test_heartbeat_response_accepts_one_structured_command() -> None:
    response = HeartbeatResponse(
        server_time=datetime(2026, 5, 24, 13, 20, 30, tzinfo=UTC),
        next_poll_after_seconds=10,
        command=Command(
            id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
            kind=CommandKind.EXEC,
            name="network_interfaces",
            args={},
            timeout_seconds=30,
        ),
    )

    serialized = response.model_dump(mode="json")

    assert serialized["status"] == "ok"
    assert serialized["command"]["kind"] == "exec"
    assert serialized["command"]["name"] == "network_interfaces"


def test_command_result_supports_rejected_commands() -> None:
    result = CommandResult(
        command_id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
        status=CommandResultStatus.REJECTED,
        stderr="unknown command preset",
    )

    serialized = result.model_dump(mode="json")

    assert serialized["status"] == "rejected"
    assert serialized["return_code"] is None


def test_models_reject_unknown_fields() -> None:
    try:
        Command(
            id="cmd_01JY3H8V8W8P3FXDR3S2BM7M6B",
            kind=CommandKind.EXEC,
            name="network_interfaces",
            args={},
            timeout_seconds=30,
            shell="ip a",
        )
    except ValidationError as error:
        assert "shell" in str(error)
    else:
        raise AssertionError("Command model accepted an unknown field")
