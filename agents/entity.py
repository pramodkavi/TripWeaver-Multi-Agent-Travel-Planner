"""Shared agent state schema — the single source of truth passed between nodes.

Every inter-agent signal (the query, extracted intent/parameters, tool results,
routing signals, activity/status, and the composed reply) flows through this
one ``GraphState``. Nodes never talk to each other directly.
"""

from enum import Enum
from typing import List, Optional, TypedDict


class AgentActivity(str, Enum):
    """Lifecycle states the UI reflects while a turn is processed."""

    ROUTING = "ROUTING"        # graph is interpreting intent / selecting an agent
    SEARCHING = "SEARCHING"    # agent is awaiting a list/search MCP tool
    BOOKING = "BOOKING"        # agent is awaiting a booking MCP tool
    RESPONDING = "RESPONDING"  # agent is composing/streaming the answer
    CLARIFYING = "CLARIFYING"  # agent paused to ask for a missing detail


class ToolCallStatus(str, Enum):
    """Outcome of an MCP tool call."""

    NONE = "NONE"
    INVOKED = "INVOKED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class GraphState(TypedDict, total=False):
    # Conversation: alternating user/assistant strings, last item is the new query.
    messages: List[str]

    # Routing signals produced by the router.
    intent: str            # "hotel" | "flight" | "general"
    sub_action: str        # "search" | "list_all" | "book" | "general"

    # Hotel parameters.
    city: Optional[str]
    check_in: Optional[str]
    check_out: Optional[str]
    hotel_id: Optional[str]
    guest_name: Optional[str]
    guest_email: Optional[str]
    room_type: Optional[str]

    # Flight parameters.
    origin: Optional[str]
    destination: Optional[str]
    flight_date: Optional[str]
    flight_id: Optional[str]
    passenger_name: Optional[str]
    passenger_email: Optional[str]

    # Intermediate findings from MCP tools.
    hotel_results: List[dict]
    flight_results: List[dict]
    booking: Optional[dict]

    # Activity / tool-call lifecycle (for the UI to reflect).
    activity: str
    tool_status: str

    # Final composed reply.
    response_text: str
