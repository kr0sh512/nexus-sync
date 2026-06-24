# nexus-sync

a utility that allows you to manage your computers.

_Main Idea_
server can send to every client "what to do". Centralized control for all clients.

## Development

```
pip install -e .[dev]
```

## Client config

The client reads YAML config files. The server still use
`.env` for server-side settings such as `NEXUS_SYNC_CLIENT_TOKENS`.

Client config is searched in this order:

1. `$(pwd)/nexus.yml`
2. `$(pwd)/nexus.yaml`
3. `$XDG_CONFIG_HOME/nexus.yml`
4. `$XDG_CONFIG_HOME/nexus.yaml`
5. `~/.config/nexus.yml`
6. `~/.config/nexus.yaml`
7. `~/.config/nexus/config.yml`
8. `~/.config/nexus/config.yaml`

Example:

```yaml
server_url: "http://127.0.0.1:5852"
client_id: "linux-client"
client_token: "change-me-client-token"
allowed_commands:
  - name: hostname
    description: "Get the hostname of the client machine"
    cmd: "hostname"
  - name: network_interfaces
    description: "Get network interface information"
    cmd: "ip addr show"
logging_level: "INFO"
```

Template examples are available in `template/` for Linux, Windows, and Darwin.
The client reports only command `name` and `description` to the server; `cmd`
stays local to the client config.

## Current design

- API contract: [docs/api.md](docs/api.md)
- Client behavior notes: [docs/client.md](docs/client.md)
- Server behavior notes: [docs/server.md](docs/server.md)

## Server API

The server uses SQLite through SQLAlchemy by default:

```bash
NEXUS_SYNC_DATABASE_URL="sqlite:///nexus-sync.db"
```

Useful server-side handlers:

```text
POST /api/v1/client/heartbeat
GET  /api/v1/server/clients
GET  /api/v1/server/clients/{client_id}
POST /api/v1/server/clients/{client_id}/commands
GET  /api/v1/server/commands/{command_id}
```

Queue command example:

```json
{
  "name": "hostname",
  "args": {},
  "timeout_seconds": 30
}
```

Clients receive queued commands on their next heartbeat and report results in a
later heartbeat.

### To build

```
make [client|server]
```

### To test

```
pytest
```
