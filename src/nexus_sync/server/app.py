from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from nexus_sync.common import Command, CommandKind, HeartbeatRequest, HeartbeatResponse
from nexus_sync.server.config import (
    DEFAULT_COMMAND_POLL_SECONDS,
    DEFAULT_IDLE_POLL_SECONDS,
    load_client_tokens,
    load_database_url,
)
from nexus_sync.server.sqlalchemy_store import SQLAlchemyStore
from nexus_sync.server.store import Store


class CommandCreateRequest(BaseModel):
    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    timeout_seconds: int = Field(default=30, gt=0)


def create_app(
    *,
    store: Store | None = None,
    client_tokens: dict[str, str] | None = None,
) -> FastAPI:
    app = FastAPI(title="nexus-sync", version="0.1.0")
    app.state.store = store or SQLAlchemyStore(load_database_url())
    app.state.client_tokens = client_tokens if client_tokens is not None else load_client_tokens()

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST, content={"detail": error.errors()}
        )

    def authorize_token(authorization: str | None = Header(default=None)) -> str:
        if authorization is None or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="missing bearer token",
            )

        token = authorization.removeprefix("Bearer ").strip()
        owner_client_id = _client_id_for_token(app.state.client_tokens, token)
        if owner_client_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid bearer token",
            )
        return owner_client_id

    @app.post("/api/v1/client/heartbeat", response_model=HeartbeatResponse)
    def heartbeat(
        payload: HeartbeatRequest,
        token_client_id: str = Depends(authorize_token),
    ) -> HeartbeatResponse:
        if token_client_id != payload.client_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="token is not allowed for this client_id",
            )

        now = datetime.now(UTC)
        app.state.store.upsert_client(payload, now)
        app.state.store.record_command_result(payload, now)

        command = app.state.store.take_next_command(payload.client_id, now)
        return HeartbeatResponse(
            server_time=now,
            next_poll_after_seconds=(
                DEFAULT_COMMAND_POLL_SECONDS if command else DEFAULT_IDLE_POLL_SECONDS
            ),
            command=command,
        )

    @app.get("/api/v1/server/clients")
    def list_clients() -> dict[str, list[dict[str, Any]]]:
        return {
            "clients": [client.model_dump(mode="json") for client in app.state.store.list_clients()]
        }

    @app.get("/api/v1/server/clients/{client_id}")
    def get_client(client_id: str) -> dict[str, Any]:
        client = app.state.store.get_client(client_id)
        if client is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")
        return client.model_dump(mode="json")

    @app.post("/api/v1/server/clients/{client_id}/commands", status_code=status.HTTP_201_CREATED)
    def create_command(client_id: str, payload: CommandCreateRequest) -> dict[str, Any]:
        if app.state.store.get_client(client_id) is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="client not found")

        return _enqueue_command(
            store=app.state.store,
            client_id=client_id,
            name=payload.name,
            args=payload.args,
            timeout_seconds=payload.timeout_seconds,
        )

    @app.get("/api/v1/server/commands/{command_id}")
    def get_command(command_id: str) -> dict[str, Any]:
        command = app.state.store.get_command(command_id)
        if command is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="command not found")

        body = command.model_dump(mode="json")
        result = app.state.store.get_command_result(command_id)
        body["result"] = result.model_dump(mode="json") if result else None
        return body

    return app


def _client_id_for_token(client_tokens: dict[str, str], token: str) -> str | None:
    for client_id, expected_token in client_tokens.items():
        if token == expected_token:
            return client_id
    return None


def _enqueue_command(
    *,
    store: Store,
    client_id: str,
    name: str,
    args: dict[str, Any],
    timeout_seconds: int,
) -> dict[str, Any]:
    now = datetime.now(UTC)
    command = Command(
        id=f"cmd_{uuid4().hex}",
        kind=CommandKind.EXEC,
        name=name,
        args=args,
        timeout_seconds=timeout_seconds,
    )
    record = store.enqueue_command(command, client_id, now)
    return record.model_dump(mode="json")


app = create_app()
