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
- CLI usage: [docs/cli.md](docs/cli.md)

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

## CLI

Install the package in editable mode to use the server API CLI:

```bash
pip install -e .
nexus-cli --help
```

Common commands:

```bash
nexus-cli --list
nexus-cli --server-url http://127.0.0.1:5852 --list
nexus-cli client linux-client
nexus-cli client linux-client --run-command hostname
nexus-cli client linux-client --run-command hostname --timeout-seconds 30
nexus-cli command cmd_123
nexus-cli --json command cmd_123
```

The CLI uses only server-side API handlers. Queued commands are delivered to the
client on its next heartbeat.

### To build

Use `doit` for repeatable checks and package builds:

```bash
pip install -e .[dev]
doit list
doit wheel      # build dist/nexus_sync-0.1.0-py3-none-any.whl
doit package    # build wheel and sdist
doit            # run tests, typecheck, format check, and wheel build
```

PyInstaller standalone binaries are still available through Makefile targets:

```
make [client|server|cli]
```

## systemd templates

Template units are available in:

```text
template/systemd/nexus-sync-server.service
template/systemd/nexus-sync-client.service
template/systemd/nexus-sync-client.timer
```

Replace `ExecStart` with the absolute path to your built binary or script before installing.
For example:

```ini
ExecStart=/opt/nexus-sync/nexus-sync-server
```

The client is a oneshot service triggered by a timer every minute.

### Install server service

```bash
sudo install -Dm644 template/systemd/nexus-sync-server.service \
  /etc/systemd/system/nexus-sync-server.service
sudo editor /etc/systemd/system/nexus-sync-server.service
sudo mkdir -p /var/lib/nexus-sync
sudo systemctl daemon-reload
sudo systemctl enable --now nexus-sync-server.service
```

Optional server env file used by the template:

```bash
sudo install -Dm600 .env.example /etc/nexus-sync/server.env
sudo editor /etc/nexus-sync/server.env
sudo systemctl restart nexus-sync-server.service
```

### Install client timer

```bash
sudo install -Dm644 template/systemd/nexus-sync-client.service \
  /etc/systemd/system/nexus-sync-client.service
sudo install -Dm644 template/systemd/nexus-sync-client.timer \
  /etc/systemd/system/nexus-sync-client.timer
sudo editor /etc/systemd/system/nexus-sync-client.service
sudo systemctl daemon-reload
sudo systemctl enable --now nexus-sync-client.timer
```

Install the client YAML config separately, for example:

```bash
sudo install -Dm600 template/linux-config.yaml /root/.config/nexus/config.yaml
sudo editor /root/.config/nexus/config.yaml
```

Check status and logs:

```bash
systemctl status nexus-sync-server.service
systemctl list-timers nexus-sync-client.timer
journalctl -u nexus-sync-server.service -f
journalctl -u nexus-sync-client.service -f
```

### To test

```
pytest
```
