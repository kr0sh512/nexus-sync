import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from types import TracebackType
from typing import Any, Protocol, Self

DEFAULT_SERVER_URL = "http://127.0.0.1:5852"
API_PREFIX = "/api/v1"
JsonObject = dict[str, Any]
Requester = Callable[[str, str, JsonObject | None], JsonObject]


class HTTPResponse(Protocol):
    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None: ...

    def read(self) -> bytes: ...


Opener = Callable[[urllib.request.Request], HTTPResponse]


class CLIError(RuntimeError):
    pass


def request_json(
    method: str,
    url: str,
    payload: JsonObject | None = None,
    *,
    opener: Opener = urllib.request.urlopen,
) -> JsonObject:
    data = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with opener(request) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        detail = error.read().decode(errors="replace")
        raise CLIError(f"HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise CLIError(f"request failed: {error.reason}") from error
    except OSError as error:
        raise CLIError(f"request failed: {error}") from error

    try:
        result = json.loads(body.decode())
    except json.JSONDecodeError as error:
        raise CLIError(f"server returned invalid JSON: {error}") from error
    if not isinstance(result, dict):
        raise CLIError("server returned JSON that is not an object")
    return result


def format_clients(payload: JsonObject) -> str:
    clients = payload.get("clients", [])
    if not isinstance(clients, list) or not clients:
        return "clients:\n- none"

    lines = ["clients:"]
    for item in clients:
        if not isinstance(item, dict):
            continue
        parts = [
            str(item.get("id", "<unknown>")),
            str(item.get("platform", "unknown")),
            str(item.get("hostname", "unknown")),
            f"version={item.get('version', 'unknown')}",
            f"last_seen={item.get('last_seen_at', 'unknown')}",
        ]
        lines.append(f"- {'  '.join(parts)}")
        commands = _command_names(item.get("available_commands", []))
        if commands:
            lines.append(f"  commands: {', '.join(commands)}")
    return "\n".join(lines)


def format_client(payload: JsonObject) -> str:
    lines = [
        f"id: {payload.get('id', '<unknown>')}",
        f"hostname: {payload.get('hostname', 'unknown')}",
        f"platform: {payload.get('platform', 'unknown')}",
        f"version: {payload.get('version', 'unknown')}",
        f"created_at: {payload.get('created_at', 'unknown')}",
        f"last_seen_at: {payload.get('last_seen_at', 'unknown')}",
        "available_commands:",
    ]
    commands = payload.get("available_commands", [])
    if not isinstance(commands, list) or not commands:
        lines.append("- none")
        return "\n".join(lines)

    for command in commands:
        if isinstance(command, dict):
            name = command.get("name", "<unknown>")
            description = command.get("description", "")
            suffix = f" - {description}" if description else ""
            lines.append(f"- {name}{suffix}")
    return "\n".join(lines)


def format_command(payload: JsonObject, *, queued: bool = False) -> str:
    lines = ["queued command:" if queued else "command:"]
    for key in (
        "id",
        "client_id",
        "kind",
        "name",
        "status",
        "timeout_seconds",
        "created_at",
        "delivered_at",
        "finished_at",
    ):
        if key in payload:
            lines.append(f"{key}: {payload.get(key)}")

    result = payload.get("result")
    if isinstance(result, dict):
        lines.append("result:")
        if "status" in result:
            lines.append(f"  status: {result.get('status')}")
        if "return_code" in result:
            lines.append(f"  return_code: {result.get('return_code')}")
        lines.append("  stdout:")
        lines.extend(_indent_block(str(result.get("stdout", ""))))
        lines.append("  stderr:")
        lines.extend(_indent_block(str(result.get("stderr", ""))))
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexus-cli", description="CLI for nexus-sync server API")
    parser.add_argument(
        "--server-url", "-s", default=DEFAULT_SERVER_URL, help="nexus-sync server URL"
    )
    parser.add_argument("--list", action="store_true", help="list clients")
    parser.add_argument("--json", action="store_true", help="print raw JSON response")

    subparsers = parser.add_subparsers(dest="resource")
    client = subparsers.add_parser("client", help="show client info or queue a command")
    client.add_argument("id", help="client id")
    client.add_argument("--run-command", metavar="NAME", help="queue a command for this client")
    client.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
        help="command timeout in seconds for --run-command",
    )

    command = subparsers.add_parser("command", help="show command execution info")
    command.add_argument("id", help="command id")
    return parser


def main(
    argv: list[str] | None = None,
    *,
    requester: Requester = request_json,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    server_url = str(args.server_url).rstrip("/")

    try:
        if args.list:
            payload = requester("GET", f"{server_url}{API_PREFIX}/server/clients", None)
            _print_payload(payload, raw_json=args.json, formatter=format_clients)
            return 0

        if args.resource == "client":
            client_id = urllib.parse.quote(str(args.id), safe="")
            if args.run_command:
                payload = requester(
                    "POST",
                    f"{server_url}{API_PREFIX}/server/clients/{client_id}/commands",
                    {
                        "name": args.run_command,
                        "args": {},
                        "timeout_seconds": args.timeout_seconds,
                    },
                )
                _print_payload(
                    payload,
                    raw_json=args.json,
                    formatter=lambda value: format_command(value, queued=True),
                )
                return 0

            payload = requester("GET", f"{server_url}{API_PREFIX}/server/clients/{client_id}", None)
            _print_payload(payload, raw_json=args.json, formatter=format_client)
            return 0

        if args.resource == "command":
            command_id = urllib.parse.quote(str(args.id), safe="")
            payload = requester(
                "GET", f"{server_url}{API_PREFIX}/server/commands/{command_id}", None
            )
            _print_payload(payload, raw_json=args.json, formatter=format_command)
            return 0
    except CLIError as error:
        print(f"nexus-cli error: {error}", file=sys.stderr)
        return 1

    parser.print_help()
    return 2


def _print_payload(
    payload: JsonObject,
    *,
    raw_json: bool,
    formatter: Callable[[JsonObject], str],
) -> None:
    if raw_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    print(formatter(payload))


def _command_names(commands: object) -> list[str]:
    if not isinstance(commands, list):
        return []
    names = []
    for command in commands:
        if isinstance(command, dict) and command.get("name"):
            names.append(str(command["name"]))
    return names


def _indent_block(value: str) -> list[str]:
    if not value:
        return ["    <empty>"]
    return [f"    {line}" if line else "" for line in value.rstrip("\n").splitlines()]


if __name__ == "__main__":
    raise SystemExit(main())
