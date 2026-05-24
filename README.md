# nexus-sync

a utility that allows you to manage your computers.

*Main Idea*
server can send to every client "what to do". Centralized control for all clients.

## Development

```
pip install -e .[dev]
```

## Current design

- API contract: [docs/api.md](docs/api.md)
- Client behavior notes: [docs/client.md](docs/client.md)
- Server behavior notes: [docs/server.md](docs/server.md)

### To build

```
make [client|server]
```


### To test

```
pytest
```
