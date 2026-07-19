"""Graph nodes: the intent router, the Hotel/Flight/General agents, and the
response composer.

Agents only reach data through MCP tools, ask a follow-up when a required field
is missing, and never invent hotel or flight details.
"""

from functools import lru_cache
from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from .entity import AgentActivity, GraphState, ToolCallStatus
from .llm import get_llm
from .mcp_client import call_tool
from .prompts import get_extraction_prompt, get_general_qa_prompt


class TravelExtraction(BaseModel):
    intent: Literal["hotel", "flight", "general"] = Field(
        default="general", description="Main user intent."
    )
    sub_action: Literal["search", "list_all", "book", "general"] = Field(
        default="general", description="Action type."
    )
    city: Optional[str] = Field(default=None, description="Hotel city name.")
    check_in: Optional[str] = Field(default=None, description="Check-in date YYYY-MM-DD.")
    check_out: Optional[str] = Field(default=None, description="Check-out date YYYY-MM-DD.")
    origin: Optional[str] = Field(default=None, description="Flight origin city/airport code.")
    destination: Optional[str] = Field(default=None, description="Flight destination city/airport code.")
    flight_date: Optional[str] = Field(default=None, description="Flight date YYYY-MM-DD.")
    hotel_id: Optional[str] = Field(default=None, description="Hotel id to book.")
    guest_name: Optional[str] = Field(default=None, description="Guest full name.")
    guest_email: Optional[str] = Field(default=None, description="Guest email.")
    room_type: Optional[str] = Field(default=None, description="Room type e.g. single/double/suite.")
    flight_id: Optional[str] = Field(default=None, description="Flight id to book.")
    passenger_name: Optional[str] = Field(default=None, description="Passenger full name.")
    passenger_email: Optional[str] = Field(default=None, description="Passenger email.")


@lru_cache(maxsize=1)
def _get_extractor():
    return get_llm().with_structured_output(TravelExtraction)


def _build_messages(system_prompt: str, history_messages: list, user_message: str) -> list:
    messages = [SystemMessage(content=system_prompt)]
    for i in range(0, len(history_messages), 2):
        messages.append(HumanMessage(content=history_messages[i]))
        if i + 1 < len(history_messages):
            messages.append(AIMessage(content=history_messages[i + 1]))
    messages.append(HumanMessage(content=user_message))
    return messages


def router(state: GraphState) -> dict:
    messages = state.get("messages", [])
    user_message = messages[-1] if messages else ""
    history = messages[:-1]

    system_prompt = get_extraction_prompt("\n".join(history))
    invocation = _build_messages(system_prompt, history, user_message)

    try:
        data = _get_extractor().invoke(invocation).model_dump()
    except Exception:
        # Fall back to General QA rather than crash if extraction fails.
        data = {"intent": "general", "sub_action": "general"}

    return {
        "intent": data.get("intent", "general"),
        "sub_action": data.get("sub_action", "general"),
        "city": data.get("city"),
        "check_in": data.get("check_in"),
        "check_out": data.get("check_out"),
        "origin": data.get("origin"),
        "destination": data.get("destination"),
        "flight_date": data.get("flight_date"),
        "hotel_id": data.get("hotel_id"),
        "guest_name": data.get("guest_name"),
        "guest_email": data.get("guest_email"),
        "room_type": data.get("room_type"),
        "flight_id": data.get("flight_id"),
        "passenger_name": data.get("passenger_name"),
        "passenger_email": data.get("passenger_email"),
        "hotel_results": [],
        "flight_results": [],
        "booking": None,
        "activity": AgentActivity.ROUTING.value,
        "tool_status": ToolCallStatus.NONE.value,
        "response_text": "",
    }


def route_after_router(state: GraphState) -> str:
    intent = state.get("intent", "general")
    if intent == "hotel":
        return "hotel"
    if intent == "flight":
        return "flight"
    return "general"


def _format_hotel(hotel: dict) -> str:
    name = hotel.get("name", "Unknown hotel")
    city = hotel.get("city", "unknown city")
    stars = hotel.get("starRating", hotel.get("stars", "N/A"))
    price = hotel.get("pricePerNight", hotel.get("price", "N/A"))
    currency = hotel.get("currency", "USD")
    rooms = hotel.get("availableRooms", "N/A")
    hotel_id = hotel.get("_id", hotel.get("id", ""))
    id_hint = f" [id: {hotel_id}]" if hotel_id else ""
    return f"{name} in {city} — {stars}★ — {currency} {price}/night — {rooms} rooms left{id_hint}"


def _format_flight(flight: dict) -> str:
    airline = flight.get("airline", "Unknown airline")
    number = flight.get("flightNumber", "N/A")
    origin = flight.get("origin", {})
    destination = flight.get("destination", {})
    origin_str = origin.get("airport", origin) if isinstance(origin, dict) else origin
    dest_str = destination.get("airport", destination) if isinstance(destination, dict) else destination
    date = flight.get("flightDate", "unknown date")
    dep = flight.get("departureTime", "N/A")
    arr = flight.get("arrivalTime", "N/A")
    price = flight.get("price", "N/A")
    currency = flight.get("currency", "USD")
    seats = flight.get("availableSeats", "N/A")
    flight_id = flight.get("_id", flight.get("id", ""))
    id_hint = f" [id: {flight_id}]" if flight_id else ""
    return (
        f"{airline} {number} {origin_str}→{dest_str} on {date}, {dep}-{arr} "
        f"— {currency} {price} — {seats} seats{id_hint}"
    )


def _is_error(result) -> bool:
    return isinstance(result, dict) and result.get("error")


def _as_list(result, key: str) -> list:
    if isinstance(result, dict):
        return result.get(key, [])
    if isinstance(result, list):
        return result
    return []


async def hotel_node(state: GraphState) -> dict:
    sub_action = state.get("sub_action", "search")

    if sub_action == "book":
        required = {
            "hotel_id": state.get("hotel_id"),
            "guest_name": state.get("guest_name"),
            "guest_email": state.get("guest_email"),
            "check_in": state.get("check_in"),
            "check_out": state.get("check_out"),
            "room_type": state.get("room_type"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            return {
                "activity": AgentActivity.CLARIFYING.value,
                "tool_status": ToolCallStatus.NONE.value,
                "response_text": (
                    "To book that hotel I still need: "
                    + ", ".join(missing).replace("_", " ")
                    + "."
                ),
            }

        result = await call_tool(
            "book_hotel",
            {
                "hotel_id": required["hotel_id"],
                "guest_name": required["guest_name"],
                "guest_email": required["guest_email"],
                "check_in_date": required["check_in"],
                "check_out_date": required["check_out"],
                "room_type": required["room_type"],
            },
        )
        if _is_error(result):
            return {
                "activity": AgentActivity.RESPONDING.value,
                "tool_status": ToolCallStatus.FAILED.value,
                "response_text": f"I couldn't complete the hotel booking. {result.get('message', '')}".strip(),
            }
        confirmation = (
            result.get("message") or result.get("status") or "Your hotel booking is confirmed."
            if isinstance(result, dict)
            else "Your hotel booking is confirmed."
        )
        return {
            "activity": AgentActivity.RESPONDING.value,
            "tool_status": ToolCallStatus.SUCCEEDED.value,
            "booking": result if isinstance(result, dict) else {"status": "confirmed"},
            "response_text": confirmation,
        }

    if sub_action == "search" and state.get("city"):
        args = {"city": state["city"]}
        if state.get("check_in"):
            args["check_in"] = state["check_in"]
        if state.get("check_out"):
            args["check_out"] = state["check_out"]
        result = await call_tool("search_hotels", args)
    else:
        result = await call_tool("list_hotels", {})

    if _is_error(result):
        return {
            "activity": AgentActivity.RESPONDING.value,
            "tool_status": ToolCallStatus.FAILED.value,
            "response_text": result.get("message", "The hotel service is unavailable right now."),
        }

    hotels = _as_list(result, "hotels")
    if not hotels:
        return {
            "activity": AgentActivity.RESPONDING.value,
            "tool_status": ToolCallStatus.SUCCEEDED.value,
            "response_text": (
                "I couldn't find any hotels for that. Try naming a city, "
                "e.g. 'hotels in Bangkok'."
            ),
        }

    return {
        "activity": AgentActivity.RESPONDING.value,
        "tool_status": ToolCallStatus.SUCCEEDED.value,
        "hotel_results": hotels,
        "response_text": "",
    }


async def flight_node(state: GraphState) -> dict:
    sub_action = state.get("sub_action", "search")

    if sub_action == "book":
        required = {
            "flight_id": state.get("flight_id"),
            "passenger_name": state.get("passenger_name"),
            "passenger_email": state.get("passenger_email"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            return {
                "activity": AgentActivity.CLARIFYING.value,
                "tool_status": ToolCallStatus.NONE.value,
                "response_text": (
                    "To book that flight I still need: "
                    + ", ".join(missing).replace("_", " ")
                    + "."
                ),
            }

        result = await call_tool("book_flight", required)
        if _is_error(result):
            return {
                "activity": AgentActivity.RESPONDING.value,
                "tool_status": ToolCallStatus.FAILED.value,
                "response_text": f"I couldn't complete the flight booking. {result.get('message', '')}".strip(),
            }
        confirmation = (
            result.get("message") or result.get("status") or "Your flight booking is confirmed."
            if isinstance(result, dict)
            else "Your flight booking is confirmed."
        )
        return {
            "activity": AgentActivity.RESPONDING.value,
            "tool_status": ToolCallStatus.SUCCEEDED.value,
            "booking": result if isinstance(result, dict) else {"status": "confirmed"},
            "response_text": confirmation,
        }

    origin = state.get("origin")
    destination = state.get("destination")

    if sub_action == "search":
        if origin and destination:
            args = {"origin": origin, "destination": destination}
            if state.get("flight_date"):
                args["date"] = state["flight_date"]
            result = await call_tool("search_flights", args)
        elif origin or destination:
            return {
                "activity": AgentActivity.CLARIFYING.value,
                "tool_status": ToolCallStatus.NONE.value,
                "response_text": (
                    "I need both a departure and a destination. "
                    "For example: 'flights from CMB to BKK'."
                ),
            }
        else:
            result = await call_tool("list_flights", {})
    else:
        result = await call_tool("list_flights", {})

    if _is_error(result):
        return {
            "activity": AgentActivity.RESPONDING.value,
            "tool_status": ToolCallStatus.FAILED.value,
            "response_text": result.get("message", "The flight service is unavailable right now."),
        }

    flights = _as_list(result, "flights")
    if not flights:
        return {
            "activity": AgentActivity.RESPONDING.value,
            "tool_status": ToolCallStatus.SUCCEEDED.value,
            "response_text": (
                "I couldn't find flights for that route. Try another route "
                "or ask to see all flights."
            ),
        }

    return {
        "activity": AgentActivity.RESPONDING.value,
        "tool_status": ToolCallStatus.SUCCEEDED.value,
        "flight_results": flights,
        "response_text": "",
    }


def general_qa_node(state: GraphState) -> dict:
    messages = state.get("messages", [])
    user_message = messages[-1] if messages else ""
    history = messages[:-1]

    system_prompt = get_general_qa_prompt("\n".join(history))
    invocation = _build_messages(system_prompt, history, user_message)

    try:
        response = get_llm().invoke(invocation)
        text = response.content
    except Exception:
        text = (
            "I'm having trouble responding right now. I can help you search or "
            "book hotels and flights — try asking about a city or a route."
        )

    return {
        "activity": AgentActivity.RESPONDING.value,
        "tool_status": ToolCallStatus.NONE.value,
        "response_text": text,
    }


def generate_response(state: GraphState) -> dict:
    if state.get("response_text"):
        # Keep a CLARIFYING signal so the UI knows the turn ended with a question.
        activity = state.get("activity")
        if activity != AgentActivity.CLARIFYING.value:
            activity = AgentActivity.RESPONDING.value
        return {
            "activity": activity,
            "response_text": state["response_text"],
        }

    hotels = state.get("hotel_results", [])
    flights = state.get("flight_results", [])

    if hotels:
        count = len(hotels)
        lines = [f"{i}. {_format_hotel(h)}" for i, h in enumerate(hotels[:5], 1)]
        text = f"I found {count} hotel option{'s' if count != 1 else ''}:\n" + "\n".join(lines)
        return {"activity": AgentActivity.RESPONDING.value, "response_text": text}

    if flights:
        count = len(flights)
        lines = [f"{i}. {_format_flight(f)}" for i, f in enumerate(flights[:5], 1)]
        text = f"I found {count} flight option{'s' if count != 1 else ''}:\n" + "\n".join(lines)
        return {"activity": AgentActivity.RESPONDING.value, "response_text": text}

    return {
        "activity": AgentActivity.RESPONDING.value,
        "response_text": "I couldn't find matching travel options.",
    }
