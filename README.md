# nexus-sync

a utility that allows you to manage your computers.

*Main Idea*
server can send to every client "what to do". Centralized control for all clients.

## Server-side

- (to future) works in docker container
- accept connections on _some_ port with correct uuid from client
- works via API requests
- use _some_ database

## Client-side

- with _some_ period of time, send info to the server
- if server want client to execute some command
  - decrease fetch time period
  - execute command
  - send result back to the server
