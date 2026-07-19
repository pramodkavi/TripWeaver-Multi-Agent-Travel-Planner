"""FastAPI backend.

Exposes the LangGraph workflow over HTTP. ``/chat`` streams Server-Sent Events
(activity cues, tool status, response tokens, then the structured results) so
the UI can show progress as it happens. All config comes from environment
variables, and external services are only reached through the MCP layer.
"""

import asyncio
import json
import os
import re
from contextlib import asynccontextmanager
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from agents.entity import AgentActivity, ToolCallStatus
from agents.graph import graph
from agents.mcp_client import call_tool, get_tool_map

load_dotenv(override=True)

MAX_HISTORY_PAIRS = int(os.getenv("MAX_HISTORY_PAIRS", "3"))
TOKEN_DELAY = float(os.getenv("STREAM_TOKEN_DELAY", "0.02"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Warm up tool discovery, but don't let a down server block startup.
    try:
        await get_tool_map()
    except Exception:
        pass
    yield


app = FastAPI(title="TripWeaver API", lifespan=lifespan)

_cors = os.getenv("CORS_ALLOW_ORIGINS", "*")
_origins = ["*"] if _cors.strip() == "*" else [o.strip() for o in _cors.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str
    # Prior turns as [user, assistant] pairs.
    history: Optional[List[List[Optional[str]]]] = None


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


def _build_messages(message: str, history: Optional[List[List[Optional[str]]]]) -> List[str]:
    flat: List[str] = []
    for pair in (history or [])[-MAX_HISTORY_PAIRS:]:
        if not pair:
            continue
        if len(pair) >= 1 and pair[0]:
            flat.append(pair[0])
        if len(pair) >= 2 and pair[1]:
            flat.append(pair[1])
    flat.append(message)
    return flat


_CUES = {
    ("hotel", "search"): (AgentActivity.SEARCHING, "Searching hotel suggestions…"),
    ("hotel", "list_all"): (AgentActivity.SEARCHING, "Fetching available hotels…"),
    ("hotel", "book"): (AgentActivity.BOOKING, "Booking your hotel…"),
    ("flight", "search"): (AgentActivity.SEARCHING, "Searching flights…"),
    ("flight", "list_all"): (AgentActivity.SEARCHING, "Fetching available flights…"),
    ("flight", "book"): (AgentActivity.BOOKING, "Booking your flight…"),
}


def _cue_for(intent: str, sub_action: str):
    if intent == "general":
        return (AgentActivity.RESPONDING, "Thinking…")
    return _CUES.get((intent, sub_action), (AgentActivity.SEARCHING, "Working on it…"))


def _tokenize(text: str) -> List[str]:
    return re.findall(r"\S+\s*|\s+", text) or [text]


async def _event_stream(message: str, history):
    yield _sse({"type": "activity", "activity": AgentActivity.ROUTING.value,
                "label": "Understanding your request…"})

    state = {"messages": _build_messages(message, history)}
    final: dict = {}

    try:
        async for chunk in graph.astream(state, stream_mode="updates"):
            for node, update in chunk.items():
                update = update or {}
                final.update(update)

                if node == "router":
                    activity, label = _cue_for(
                        update.get("intent", "general"),
                        update.get("sub_action", "general"),
                    )
                    yield _sse({"type": "activity", "activity": activity.value, "label": label})

                elif node in ("hotel", "flight", "general"):
                    status = update.get("tool_status")
                    if status in (ToolCallStatus.SUCCEEDED.value, ToolCallStatus.FAILED.value):
                        yield _sse({"type": "tool", "status": status})
                    activity = update.get("activity")
                    if activity == AgentActivity.CLARIFYING.value:
                        yield _sse({"type": "activity", "activity": activity})
    except Exception:
        yield _sse({"type": "error",
                    "message": "Something went wrong while planning your trip. Please try again."})
        yield _sse({"type": "done"})
        return

    text = final.get("response_text") or "I couldn't process that request."
    yield _sse({"type": "activity", "activity": AgentActivity.RESPONDING.value})
    for token in _tokenize(text):
        yield _sse({"type": "token", "text": token})
        if TOKEN_DELAY:
            await asyncio.sleep(TOKEN_DELAY)

    yield _sse({
        "type": "result",
        "hotels": final.get("hotel_results") or [],
        "flights": final.get("flight_results") or [],
        "booking": final.get("booking"),
    })
    yield _sse({"type": "done"})


@app.get("/")
async def root():
    return {"service": "TripWeaver API", "status": "ok"}


@app.get("/health")
async def health():
    try:
        tools = await get_tool_map()
        names = sorted(tools.keys())
    except Exception:
        names = []
    return {
        "status": "ok",
        "mcp_tools": names,
        "hotel_service": any(n.endswith("hotels") or n == "book_hotel" for n in names),
        "flight_service": any(n.endswith("flights") or n == "book_flight" for n in names),
    }


@app.get("/hotels")
async def list_hotels():
    return await call_tool("list_hotels", {})


@app.get("/flights")
async def list_flights():
    return await call_tool("list_flights", {})


@app.post("/chat")
async def chat(request: ChatRequest):
    return StreamingResponse(
        _event_stream(request.message, request.history),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=os.getenv("BACKEND_HOST", "0.0.0.0"),
        port=int(os.getenv("BACKEND_PORT", "8000")),
    )
