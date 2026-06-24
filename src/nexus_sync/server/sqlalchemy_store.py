from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import Column, MetaData, String, Table, create_engine, select
from sqlalchemy.engine import Engine

from nexus_sync.common import (
    ClientRecord,
    Command,
    CommandRecord,
    CommandResultRecord,
    CommandStatus,
    HeartbeatRequest,
)
from nexus_sync.server.store import TERMINAL_COMMAND_STATUSES


class SQLAlchemyStore:
    def __init__(self, database_url: str = "sqlite:///nexus-sync.db") -> None:
        self.engine = create_engine(database_url)
        self.metadata = MetaData()
        self.clients = Table(
            "clients",
            self.metadata,
            Column("id", String, primary_key=True),
            Column("json", String, nullable=False),
        )
        self.commands = Table(
            "commands",
            self.metadata,
            Column("id", String, primary_key=True),
            Column("client_id", String, nullable=False, index=True),
            Column("status", String, nullable=False, index=True),
            Column("created_at", String, nullable=False, index=True),
            Column("json", String, nullable=False),
        )
        self.results = Table(
            "command_results",
            self.metadata,
            Column("command_id", String, primary_key=True),
            Column("json", String, nullable=False),
        )
        self.metadata.create_all(self.engine)

    def list_clients(self) -> list[ClientRecord]:
        with self.engine.begin() as connection:
            rows = connection.execute(select(self.clients.c.json).order_by(self.clients.c.id)).all()
        return [ClientRecord.model_validate_json(row.json) for row in rows]

    def get_client(self, client_id: str) -> ClientRecord | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(self.clients.c.json).where(self.clients.c.id == client_id)
            ).first()
        return ClientRecord.model_validate_json(row.json) if row else None

    def upsert_client_from_payload(self, payload: dict, now: datetime) -> ClientRecord:
        return self.upsert_client(HeartbeatRequest.model_validate(payload), now)

    def upsert_client(self, heartbeat: HeartbeatRequest, now: datetime) -> ClientRecord:
        existing = self.get_client(heartbeat.client_id)
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
        with self.engine.begin() as connection:
            connection.execute(self.clients.delete().where(self.clients.c.id == record.id))
            connection.execute(
                self.clients.insert().values(id=record.id, json=record.model_dump_json())
            )
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
        self._write_command(record)
        return record

    def record_command_result_from_payload(self, payload: dict, now: datetime) -> None:
        self.record_command_result(HeartbeatRequest.model_validate(payload), now)

    def record_command_result(self, heartbeat: HeartbeatRequest, now: datetime) -> None:
        result = heartbeat.last_command_result
        if result is None:
            return

        command = self.get_command(result.command_id)
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
        self._write_command(
            command.model_copy(
                update={
                    "status": CommandStatus(result.status.value),
                    "finished_at": finished_at,
                }
            )
        )
        record = CommandResultRecord(
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
        with self.engine.begin() as connection:
            connection.execute(
                self.results.delete().where(self.results.c.command_id == record.command_id)
            )
            connection.execute(
                self.results.insert().values(
                    command_id=record.command_id,
                    json=record.model_dump_json(),
                )
            )

    def take_next_command(self, client_id: str, now: datetime) -> Command | None:
        with self.engine.begin() as connection:
            rows = connection.execute(
                select(self.commands.c.json)
                .where(self.commands.c.client_id == client_id)
                .where(self.commands.c.status == CommandStatus.PENDING.value)
                .order_by(self.commands.c.created_at)
            ).all()
        if not rows:
            return None

        record = CommandRecord.model_validate_json(rows[0].json)
        delivered = record.model_copy(
            update={
                "status": CommandStatus.DELIVERED,
                "attempts": record.attempts + 1,
                "delivered_at": now,
            }
        )
        self._write_command(delivered)
        return Command(
            id=delivered.id,
            kind=delivered.kind,
            name=delivered.name,
            args=delivered.args,
            timeout_seconds=delivered.timeout_seconds,
        )

    def get_command(self, command_id: str) -> CommandRecord | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(self.commands.c.json).where(self.commands.c.id == command_id)
            ).first()
        return CommandRecord.model_validate_json(row.json) if row else None

    def get_command_result(self, command_id: str) -> CommandResultRecord | None:
        with self.engine.begin() as connection:
            row = connection.execute(
                select(self.results.c.json).where(self.results.c.command_id == command_id)
            ).first()
        return CommandResultRecord.model_validate_json(row.json) if row else None

    def _write_command(self, record: CommandRecord) -> None:
        with self.engine.begin() as connection:
            connection.execute(self.commands.delete().where(self.commands.c.id == record.id))
            connection.execute(
                self.commands.insert().values(
                    id=record.id,
                    client_id=record.client_id,
                    status=record.status.value,
                    created_at=record.created_at.isoformat(),
                    json=record.model_dump_json(),
                )
            )
