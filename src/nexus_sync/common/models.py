from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ClientPlatform(StrEnum):
    LINUX = "linux"
    DARWIN = "darwin"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


class CommandKind(StrEnum):
    EXEC = "exec"


class CommandResultStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


class CommandStatus(StrEnum):
    PENDING = "pending"
    DELIVERED = "delivered"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED = "rejected"


class ClientInfo(StrictBaseModel):
    hostname: str
    platform: ClientPlatform
    version: str


class ClientState(StrictBaseModel):
    local_time: datetime
    uptime_seconds: int | None = Field(default=None, ge=0)


class CommandResult(StrictBaseModel):
    command_id: str
    status: CommandResultStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    return_code: int | None = None
    stdout: str = ""
    stderr: str = ""


class HeartbeatRequest(StrictBaseModel):
    client_id: str
    observed_at: datetime
    client: ClientInfo
    state: ClientState
    last_command_result: CommandResult | None = None


class Command(StrictBaseModel):
    id: str
    kind: CommandKind
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(gt=0)


class HeartbeatResponse(StrictBaseModel):
    status: Literal["ok"] = "ok"
    server_time: datetime
    next_poll_after_seconds: int = Field(ge=0)
    command: Command | None = None


class ClientRecord(StrictBaseModel):
    id: str
    hostname: str
    platform: ClientPlatform
    version: str
    created_at: datetime
    last_seen_at: datetime
    is_active: bool = True
    token_hash: str | None = None


class CommandRecord(StrictBaseModel):
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
    id: str
    actor: str
    action: str
    subject_type: str
    subject_id: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)
