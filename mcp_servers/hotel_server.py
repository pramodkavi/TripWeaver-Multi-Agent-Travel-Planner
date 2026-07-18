"""Hotel MCP server (FastMCP, streamable-http).

Exposes the hotel travel capabilities as MCP tools: ``list_hotels``,
``search_hotels`` and ``book_hotel``. Results are passed through with full
fidelity (no field trimming) so agents can recommend and book reliably.

Run (from the module root):
    python -m mcp_servers.hotel_server
or:
    python mcp_servers/hotel_server.py

Host/port come from env (HOTEL_MCP_HOST / HOTEL_MCP_PORT); the upstream service
URL comes from TRAVEL_SERVICE_BASE_URL.
"""

import os
from typing import Optional

from mcp.server.fastmcp import FastMCP

try:  # works when run as a module: python -m mcp_servers.hotel_server
    from mcp_servers.upstream import get_json, post_json
except ImportError:  # works when run as a script: python mcp_servers/hotel_server.py
    from upstream import get_json, post_json


HOST = os.getenv("HOTEL_MCP_HOST", "127.0.0.1")
PORT = int(os.getenv("HOTEL_MCP_PORT", "8001"))

mcp = FastMCP("Hotel Service", host=HOST, port=PORT)


@mcp.tool()
def list_hotels() -> dict:
    """List all available hotels with full details.

    Use when the traveller asks to see or list all hotels without naming a
    city. Returns ``{"hotels": [...]}`` where each hotel includes id, name,
    address, city, country, price per night, currency, star rating, available
    rooms and amenities. On failure returns ``{"error": true, "message": ...}``.
    """
    return get_json("/hotels")


@mcp.tool()
def search_hotels(
    city: str,
    check_in: Optional[str] = None,
    check_out: Optional[str] = None,
) -> dict:
    """Search hotels in a city, optionally for a date range.

    Args:
        city: City name to search, e.g. "Bangkok", "Colombo", "Singapore".
        check_in: Optional check-in date (YYYY-MM-DD).
        check_out: Optional check-out date (YYYY-MM-DD).

    Returns ``{"hotels": [...]}`` with full hotel details, or a structured
    error payload if the service is unavailable.
    """
    params = {"city": city}
    if check_in:
        params["checkIn"] = check_in
    if check_out:
        params["checkOut"] = check_out
    return get_json("/hotels/search", params=params)


@mcp.tool()
def book_hotel(
    hotel_id: str,
    guest_name: str,
    guest_email: str,
    check_in_date: str,
    check_out_date: str,
    room_type: str,
) -> dict:
    """Book a hotel room and return the service's confirmation.

    Args:
        hotel_id: ID of the hotel to book (the ``_id`` from a search result).
        guest_name: Full name of the guest.
        guest_email: Contact email for the guest.
        check_in_date: Check-in date (YYYY-MM-DD).
        check_out_date: Check-out date (YYYY-MM-DD).
        room_type: Room type, e.g. "single", "double", "suite".

    Returns the booking confirmation from the service, or a structured error
    payload if the booking is rejected or the service is unavailable.
    """
    payload = {
        "hotelId": hotel_id,
        "guestName": guest_name,
        "guestEmail": guest_email,
        "checkInDate": check_in_date,
        "checkOutDate": check_out_date,
        "roomType": room_type,
    }
    return post_json("/hotels/book", payload)


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
