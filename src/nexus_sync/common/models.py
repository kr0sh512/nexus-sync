from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    """Base model that rejects unknown fields (``extra='forbid'``)."""

    model_config = ConfigDict(extra="forbid")


class ClientPlatform(StrEnum):
    """Operating-system family reported by a client."""

    LINUX = "linux"
    DARWIN = "darwin"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


class CommandKind(StrEnum):
    """Type of executor a command targets (only ``exec`` is defined so far)."""

    EXEC = "exec"


class CommandResultStatus(StrEnum):
    """Terminal outcome a client reports for an executed command."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


class CommandStatus(StrEnum):
    """Lifecycle state of a command on the server (pending → delivered → terminal)."""

    PENDING = "pending"
    DELIVERED = "delivered"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


class ClientInfo(StrictBaseModel):
    """Identifying details a client reports about itself in a heartbeat."""

    hostname: str
    platform: ClientPlatform
    version: str


class ClientState(StrictBaseModel):
    """Lightweight runtime state a client reports (local time, uptime)."""

    local_time: datetime
    uptime_seconds: int | None = Field(default=None, ge=0)


class ClientCommandCapability(StrictBaseModel):
    """A command preset a client advertises as runnable (name and description)."""

    name: str
    description: str


class CommandResult(StrictBaseModel):
    """Outcome of one executed command, sent by the client to the server."""

    command_id: str
    status: CommandResultStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""


class HeartbeatRequest(StrictBaseModel):
    """Payload a client POSTs each poll: identity, state, capabilities, last result."""

    client_id: str
    observed_at: datetime
    client: ClientInfo
    state: ClientState
    available_commands: list[ClientCommandCapability] = Field(default_factory=list)
    last_command_result: CommandResult | None = None


class Command(StrictBaseModel):
    """A command the server hands to a client for execution."""

    id: str
    kind: CommandKind
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(gt=0)


class HeartbeatResponse(StrictBaseModel):
    """Server reply to a heartbeat: poll interval and an optional command to run."""

    status: Literal["ok"] = "ok"
    server_time: datetime
    next_poll_after_seconds: int = Field(ge=0)
    command: Command | None = None


class ClientRecord(StrictBaseModel):
    """Server-side stored view of a client and its last heartbeat."""

    id: str
    hostname: str
    platform: ClientPlatform
    version: str
    created_at: datetime
    last_seen_at: datetime
    is_active: bool = True
    token_hash: str | None = None
    available_commands: list[ClientCommandCapability] = Field(default_factory=list)


class CommandRecord(StrictBaseModel):
    """Server-side stored command with delivery and lifecycle bookkeeping."""

    id: str
    client_id: str
    kind: CommandKind
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    status: CommandStatus = CommandStatus.PENDING
    timeout_seconds: int = Field(gt=0)
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=1, ge=1)
    created_at: datetime
    delivered_at: datetime | None = None
    finished_at: datetime | None = None


class CommandResultRecord(StrictBaseModel):
    """Server-side stored result reported by a client for a command."""

    command_id: str
    client_id: str
    status: CommandResultStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    received_at: datetime


class AuditLogRecord(StrictBaseModel):
    """Audit-trail entry recording who did what to which subject."""

    id: str
    actor: str
    action: str
    subject_type: str
    subject_id: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
