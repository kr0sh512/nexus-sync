# Client

The core idea - it sends its key and basic info about itself (hostname, local
time, anything else?) to a server known by ip/domain.

In response it can get either a plain "ok" or a command to execute.

It sends requests to the server at a certain frequency, gradually increasing but
dropping sharply when a command is received in the response (in case something
else needs to be executed).

There is a lower bound on the frequency (roughly 1/minute).

Example flow

```
...
client -> server: hello!, i'm $(hostname), uuid= , ts=
server -> client: ok, 200
*waits 45s*
client -> server: hello!, i'm $(hostname), uuid= , ts=
server -> client: ok, 200
*waits 46s*
client -> server: hello!, i'm $(hostname), uuid= , ts=
server -> client: ok, execute "ip a", 200
client: *execute*
client -> server: hello!, i'm $(hostname), uuid= , ts=, stdout= , stderr= , ...
*waits 23s*
```

Additional info about command execution may be needed (at least the error code).

+ the set of allowed commands should probably be limited on the client
+ encryption / server identification should be considered explicitly

## Allowed commands

The client runs only the commands described in its local YAML config file. Only
`name` and `description` are sent to the server; the `cmd` field stays on the
client and is not controlled by the server.

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

The file is looked up as `nexus.yml`/`nexus.yaml` in the current directory, then
in `$XDG_CONFIG_HOME`, then in `~/.config`, then as
`~/.config/nexus/config.yml`/`.yaml`.
