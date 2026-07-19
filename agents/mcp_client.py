"""Bridge between the agents and the travel MCP servers.

Tools are discovered from the running servers (URLs from env) and called by
name, so adding or swapping a service is a config change rather than an agent
change. Each server is loaded independently and calls return a structured error
instead of raising, so one server being down does not affect the others.
"""

import json
import os

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv(override=True)


def get_server_config() -> dict:
    """MCP server connection map, driven entirely by environment variables."""
    return {
        "hotel": {
            "url": os.getenv("HOTEL_MCP_URL", "http://127.0.0.1:8001/mcp"),
            "transport": "streamable_http",
        },
        "flight": {
            "url": os.getenv("FLIGHT_MCP_URL", "http://127.0.0.1:8002/mcp"),
            "transport": "streamable_http",
        },
    }


_tool_map: dict | None = None


async def get_tool_map(force_reload: bool = False) -> dict:
    """Return ``{tool_name: BaseTool}`` discovered across the MCP servers.

    Each server is queried independently; a server that is unreachable is
    skipped (its tools absent) rather than failing the whole load.
    """
    global _tool_map
    if _tool_map is not None and not force_reload:
        return _tool_map

    client = MultiServerMCPClient(get_server_config())
    tool_map: dict = {}
    for server_name in ("hotel", "flight"):
        try:
            tools = await client.get_tools(server_name=server_name)
            for tool in tools:
                tool_map[tool.name] = tool
        except Exception:
            # Server unavailable — its tools stay absent; other agents unaffected.
            continue

    _tool_map = tool_map
    return _tool_map


def _parse_result(result):
    """Normalise an MCP tool result into a Python dict/list where possible.

    The langchain MCP adapter typically returns a list of content blocks, e.g.
    ``[{"type": "text", "text": "<json>"}]``. We concatenate the text blocks and
    parse them as JSON; other shapes (already-parsed dict/list, plain string)
    are handled as fallbacks.
    """
    if isinstance(result, list):
        texts = [
            block["text"]
            for block in result
            if isinstance(block, dict) and block.get("type") == "text" and "text" in block
        ]
        if texts:
            joined = "".join(texts)
            try:
                return json.loads(joined)
            except (ValueError, TypeError):
                return {"message": joined}
        return result  # already a plain list of values
    if isinstance(result, dict):
        return result
    if isinstance(result, str):
        try:
            return json.loads(result)
        except (ValueError, TypeError):
            return {"message": result}
    return result


async def call_tool(name: str, args: dict) -> dict | list:
    """Invoke an MCP tool by name, returning its result or a structured error.

    Never raises: transport/connection failures and missing tools come back as
    ``{"error": True, "message": ...}`` so callers can degrade gracefully.
    """
    tool_map = await get_tool_map()
    tool = tool_map.get(name)

    # A missing tool may mean the server was down at load time — retry once.
    if tool is None:
        tool_map = await get_tool_map(force_reload=True)
        tool = tool_map.get(name)

    if tool is None:
        return {
            "error": True,
            "message": "That travel service is temporarily unavailable. Please try again shortly.",
        }

    try:
        result = await tool.ainvoke(args)
        return _parse_result(result)
    except Exception as exc:
        return {
            "error": True,
            "message": "That travel service is temporarily unavailable. Please try again shortly.",
            "detail": str(exc),
        }
