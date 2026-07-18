# MCP Setup Guide

The **MCP (Model Context Protocol) layer is the single point of contact** with
external travel services. Agents never call a travel API directly — they call
MCP tools that are *discovered* at runtime. This is what keeps external services
decoupled from agent code.

## The servers

Two standalone FastMCP servers (`mcp_servers/`), each a separate process using
the `streamable-http` transport:

| Server | File | Port (default) | Tools |
|--------|------|----------------|-------|
| Hotel | `mcp_servers/hotel_server.py` | 8001 | `list_hotels`, `search_hotels`, `book_hotel` |
| Flight | `mcp_servers/flight_server.py` | 8002 | `list_flights`, `search_flights`, `book_flight` |

Both reach the real travel service through `mcp_servers/upstream.py`, which:
- reads the base URL from `TRAVEL_SERVICE_BASE_URL`,
- returns full result fields (no trimming), and
- converts **every** failure into a structured `{"error": true, "message": ...}`
  payload instead of raising — the basis for graceful degradation.

### Running the servers
```bash
python -m mcp_servers.hotel_server     # binds HOTEL_MCP_HOST:HOTEL_MCP_PORT
python -m mcp_servers.flight_server    # binds FLIGHT_MCP_HOST:FLIGHT_MCP_PORT
```

## How agents discover and call tools

`agents/mcp_client.py` uses `MultiServerMCPClient` (from
`langchain-mcp-adapters`) to connect to the servers listed in
`get_server_config()` (URLs from `HOTEL_MCP_URL` / `FLIGHT_MCP_URL`) and load
their tools:

```python
tool_map = await get_tool_map()          # {tool_name: BaseTool}, discovered live
result   = await call_tool("search_hotels", {"city": "Bangkok"})
```

- Servers are loaded **independently**, so if one is down its tools are simply
  absent and the other agent keeps working.
- `call_tool()` never raises: a missing tool or transport error returns a
  structured error dict, which the agent surfaces as a friendly message.

## Adding or swapping a service (proving the decoupling)

You can add a capability **without touching any agent code**:

1. Add a new tool to an existing server (e.g. a `filter_hotels` tool in
   `hotel_server.py`), or create a new server file and register it in
   `get_server_config()` in `agents/mcp_client.py`.
2. Restart the server(s). The agent discovers the new tool by name via
   `get_tool_map()`.

To swap the backing provider, point `TRAVEL_SERVICE_BASE_URL` at a different
service and adjust only `upstream.py` (and the server request shapes if needed).
The agents, graph, and prompts stay unchanged.

## Configuration

| Variable | Used by | Default |
|----------|---------|---------|
| `TRAVEL_SERVICE_BASE_URL` | MCP servers (`upstream.py`) | Convex demo service |
| `HOTEL_MCP_HOST` / `HOTEL_MCP_PORT` | Hotel server bind | `127.0.0.1` / `8001` |
| `FLIGHT_MCP_HOST` / `FLIGHT_MCP_PORT` | Flight server bind | `127.0.0.1` / `8002` |
| `HOTEL_MCP_URL` / `FLIGHT_MCP_URL` | Backend → MCP connection | `http://127.0.0.1:8001/mcp` / `:8002` |
