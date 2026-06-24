from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from fastapi import HTTPException, status

from nexus_sync.common import (
    ClientRecord,
    Command,
    CommandRecord,
    CommandResultRecord,
    CommandStatus,
    HeartbeatRequest,
)


class Store(Protocol):
    def upsert_client(self, heartbeat: HeartbeatRequest, now: datetime) -> ClientRecord:
        pass

    def record_command_result(self, heartbeat: HeartbeatRequest, now: datetime) -> None:
        pass

    def take_next_command(self, client_id: str, now: datetime) -> Command | None:
        pass


@dataclass
class InMemoryStore:
    clients: dict[str, ClientRecord] = field(default_factory=dict)
    commands: dict[str, CommandRecord] = field(default_factory=dict)
    results: list[CommandResultRecord] = field(default_factory=list)

    def upsert_client(self, heartbeat: HeartbeatRequest, now: datetime) -> ClientRecord:
        existing = self.clients.get(heartbeat.client_id)
        created_at = existing.created_at if existing else now
        token_hash = existing.token_hash if existing else None

        record = ClientRecord(
            id=heartbeat.client_id,
            hostname=heartbeat.client.hostname,
            platform=heartbeat.client.platform,
            version=heartbeat.client.version,
            created_at=created_at,
            last_seen_at=now,
            is_active=True,
            token_hash=token_hash,
            available_commands=heartbeat.available_commands,
        )
        self.clients[heartbeat.client_id] = record
        return record

    def enqueue_command(self, command: Command, client_id: str, now: datetime) -> CommandRecord:
        record = CommandRecord(
            id=command.id,
            client_id=client_id,
            kind=command.kind,
            name=command.name,
            args=command.args,
            status=CommandStatus.PENDING,
            timeout_seconds=command.timeout_seconds,
            created_at=now,
        )
        self.commands[record.id] = record
        return record

    def record_command_result(self, heartbeat: HeartbeatRequest, now: datetime) -> None:
        result = heartbeat.last_command_result
        if result is None:
            return

        command = self.commands.get(result.command_id)
        if command is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="command result references unknown command",
            )
        if command.client_id != heartbeat.client_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="command result references command for another client",
            )
        if command.status in TERMINAL_COMMAND_STATUSES:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="command result references terminal command",
            )

        finished_at = result.finished_at or now
        self.commands[command.id] = command.model_copy(
            update={
                "status": CommandStatus(result.status.value),
                "finished_at": finished_at,
            }
        )
        self.results.append(
            CommandResultRecord(
                command_id=result.command_id,
                client_id=heartbeat.client_id,
                status=result.status,
                started_at=result.started_at,
                finished_at=finished_at,
                return_code=result.return_code,
                stdout=result.stdout,
                stderr=result.stderr,
                received_at=now,
            )
        )

    def take_next_command(self, client_id: str, now: datetime) -> Command | None:
        pending = sorted(
            (
                command
                for command in self.commands.values()
                if command.client_id == client_id and command.status == CommandStatus.PENDING
            ),
            key=lambda command: command.created_at,
        )
        if not pending:
            return None

        record = pending[0]
        self.commands[record.id] = record.model_copy(
            update={
                "status": CommandStatus.DELIVERED,
                "attempts": record.attempts + 1,
                "delivered_at": now,
            }
        )
        return Command(
            id=record.id,
            kind=record.kind,
            name=record.name,
            args=record.args,
            timeout_seconds=record.timeout_seconds,
        )


TERMINAL_COMMAND_STATUSES = {
    CommandStatus.SUCCEEDED,
    CommandStatus.FAILED,
    CommandStatus.TIMED_OUT,
    CommandStatus.REJECTED,
}
