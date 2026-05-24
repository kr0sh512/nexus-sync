from datetime import UTC, datetime

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from nexus_sync.common import HeartbeatRequest, HeartbeatResponse
from nexus_sync.server.config import (
    DEFAULT_COMMAND_POLL_SECONDS,
    DEFAULT_IDLE_POLL_SECONDS,
    load_client_tokens,
)
from nexus_sync.server.store import InMemoryStore, Store


def create_app(
    *,
    store: Store | None = None,
    client_tokens: dict[str, str] | None = None,
) -> FastAPI:
    app = FastAPI(title="nexus-sync", version="0.1.0")
    app.state.store = store or InMemoryStore()
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

    return app


def _client_id_for_token(client_tokens: dict[str, str], token: str) -> str | None:
    for client_id, expected_token in client_tokens.items():
        if token == expected_token:
            return client_id
    return None


app = create_app()
