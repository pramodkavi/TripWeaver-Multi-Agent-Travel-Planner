"""Flight MCP server (FastMCP, streamable-http).

Exposes the flight travel capabilities as MCP tools: ``list_flights``,
``search_flights`` and ``book_flight``. Results are passed through with full
fidelity (no field trimming) so agents can plan and book reliably.

Run (from the module root):
    python -m mcp_servers.flight_server
or:
    python mcp_servers/flight_server.py

Host/port come from env (FLIGHT_MCP_HOST / FLIGHT_MCP_PORT); the upstream
service URL comes from TRAVEL_SERVICE_BASE_URL.
"""

import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

try:  # works when run as a module: python -m mcp_servers.flight_server
    from mcp_servers.upstream import get_json, post_json
except ImportError:  # works when run as a script: python mcp_servers/flight_server.py
    from upstream import get_json, post_json


HOST = os.getenv("FLIGHT_MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("FLIGHT_MCP_PORT", "8002"))

mcp = FastMCP("Flight Service", host=HOST, port=PORT)


def _normalize_code(value: str) -> str:
    """Uppercase 3-letter airport codes (e.g. 'cmb' -> 'CMB'); pass others through."""
    if value and len(value) == 3 and value.isalpha():
        return value.upper()
    return value


@mcp.tool()
def list_flights() -> dict:
    """List all available flights with full details.

    Use when the traveller asks to see or list all flights without naming a
    route. Returns ``{"flights": [...]}`` where each flight includes id,
    airline, aircraft, flight number, origin/destination (airport, city,
    country), departure/arrival times, duration, date, price, currency and
    available seats. On failure returns ``{"error": true, "message": ...}``.
    """
    return get_json("/flights")


@mcp.tool()
def search_flights(
    origin: str,
    destination: str,
    date: Optional[str] = None,
) -> dict:
    """Search flights for a route, optionally on a specific date.

    Args:
        origin: Origin city or 3-letter airport code, e.g. "CMB", "Bangkok".
        destination: Destination city or 3-letter airport code, e.g. "BKK".
        date: Optional flight date (YYYY-MM-DD).

    Returns ``{"flights": [...]}`` with full flight details, or a structured
    error payload if the service is unavailable.
    """
    params = {
        "origin": _normalize_code(origin),
        "destination": _normalize_code(destination),
    }
    if date:
        params["date"] = date
    return get_json("/flights/search", params=params)


@mcp.tool()
def book_flight(
    flight_id: str,
    passenger_name: str,
    passenger_email: str,
) -> dict:
    """Book a flight and return the service's confirmation.

    Args:
        flight_id: ID of the flight to book (the ``_id`` from a search result).
        passenger_name: Full name of the passenger.
        passenger_email: Contact email for the passenger.

    Returns the booking confirmation from the service, or a structured error
    payload if the booking is rejected or the service is unavailable.
    """
    payload = {
        "flightId": flight_id,
        "passengerName": passenger_name,
        "passengerEmail": passenger_email,
    }
    return post_json("/flights/book", payload)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
