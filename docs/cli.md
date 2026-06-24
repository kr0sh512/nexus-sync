# nexus-cli

`nexus-cli` is a small non-interactive CLI for the nexus-sync server API.

## Install for development

```bash
pip install -e .
nexus-cli --help
```

The default server URL is `http://127.0.0.1:5852`. Override it with
`--server-url` or `-s`.

## List clients

```bash
nexus-cli --list
```

## Show client info

```bash
nexus-cli client linux-client
```

The output includes basic client metadata and advertised `available_commands`.

## Queue a command for a client

```bash
nexus-cli client linux-client --run-command hostname
nexus-cli client linux-client --run-command hostname --timeout-seconds 30
```

Payload shape:

```json
{
  "name": "hostname",
  "args": {},
  "timeout_seconds": 30
}
```

## Show command execution info

```bash
nexus-cli command cmd_123
```

If the client has reported a result, stdout and stderr are printed.

## JSON output

Use `--json` for machine-readable output:

```bash
nexus-cli --json --list
nexus-cli --json client linux-client
nexus-cli --json command cmd_123
```

## Build standalone binary

```bash
make cli
```

This creates `dist/nexus-cli` through PyInstaller.

## Build wheel package

Use `doit` from the development dependencies:

```bash
pip install -e .[dev]
doit wheel
```

The wheel is written to `dist/nexus_sync-0.1.0-py3-none-any.whl` and installs the
`nexus-cli` console script.
