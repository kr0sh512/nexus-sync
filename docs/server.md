# Server

TODO:
- formally describe the whole API
- add the commands themselves, possibly as per-platform presets

## Core idea

- API endpoints. Access purely over SSL (but that's already nginx's
  responsibility).
- clients authorize with some key of their own.
  - the manual setup problem (but it seems minimal here, not too bad)
- when a client sends anything, the response should include commands to execute,
  if any.
- the client side must be configured to trust the server.

The server needs several settings

- a request rate limit (per single client, roughly)
- a limit on stored info (and whether to keep old data? yes, logs)
  - per-user limit
  - global limit
- custom commands
- tracking command delivery/execution by the server, retries, attempt limit

## Capabilities (API endpoints)

'No idea how to describe these endpoints (or rather, no desire to describe them
properly)'

### Admin endpoints

All users are treated as admins for convenience. There are no others.

1. get the list of all clients
  - with a separate "only activated" parameter
2. get data for a client
  - this includes all info about its metrics, when it was last online, and which
    commands are available for it (yes, we'll restrict them, possibly via a
    zero-trust model)
3. run some command
  - the question here is whether we'll wait for a response from our client
    (probably not)
4. obtain a token, authorization
5. add a custom command (for a client)
  - the problem is with systems if you want universal addition. The way out is
    to add it only for a single client (better all around)

### Client endpoints

Not even sure more than one will be needed

1. Send information
  - just knocks with its uuid and sends what it knows
2. Info about the server?
  - possibly fetch the ip (to knock on, if the certificate is in place), other
    domains
  - some special "rules" if the package with their installation gets lost (the
    package itself is unlikely to be lost, we'll know immediately)
