# Agent instructions for the `connector/` folder

## Do not read these files

The following files are off-limits. **Do not open, read, print, `cat`, `grep`, or otherwise
inspect their contents**, and do not include them in your context:

- `connector_client_servers/clientdocs.py`
- `connector_client_servers/data/mock.json`
- `connector_client_servers/data/prod.json`

These are the client source-system server and its data scenarios (the mock and the
"production" data the connector is graded against). Treat the client source system as an opaque
black box: interact with it only over its HTTP API (see the Swagger UI at `/docs` when the
server is running), never by reading the server code or the scenario data.

If a task seems to require their internals, stop and ask the human instead of reading the files.
