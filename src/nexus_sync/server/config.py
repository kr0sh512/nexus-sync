import os

DEFAULT_IDLE_POLL_SECONDS = 60
DEFAULT_COMMAND_POLL_SECONDS = 10
DEFAULT_DATABASE_URL = "sqlite:///nexus-sync.db"


def load_database_url() -> str:
    return os.environ.get("NEXUS_SYNC_DATABASE_URL", DEFAULT_DATABASE_URL)


def load_client_tokens() -> dict[str, str]:
    raw_tokens = os.environ.get("NEXUS_SYNC_CLIENT_TOKENS", "dev-client:dev-token")
    tokens: dict[str, str] = {}
    for item in raw_tokens.split(","):
        if not item.strip():
            continue
        client_id, separator, token = item.partition(":")
        if separator and client_id and token:
            tokens[client_id] = token
    return tokens
