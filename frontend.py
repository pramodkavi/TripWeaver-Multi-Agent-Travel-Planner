"""Gradio frontend for TripWeaver.

A travel-themed, responsive chat UI that consumes the backend's Server-Sent
Event stream so the traveller sees the agent working in real time:
- activity cues ("Searching hotel suggestions…", "Booking hotel…") act as the
  loading indicator while agents work,
- the reply streams in token-by-token,
- hotel/flight results are rendered as a clean table,
- backend/service failures surface as friendly messages, never stack traces.

Configuration comes from the environment (TRAVEL_PLANNER_API_URL).
"""

import json
import os

import gradio as gr
import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

API_URL = os.environ.get("TRAVEL_PLANNER_API_URL", "http://127.0.0.1:8000/chat")
REQUEST_TIMEOUT = float(os.environ.get("FRONTEND_TIMEOUT", "60"))
MAX_TABLE_ROWS = 8

ACTIVITY_FALLBACK = {
    "ROUTING": "Understanding your request…",
    "SEARCHING": "Searching…",
    "BOOKING": "Booking…",
    "RESPONDING": "Composing your answer…",
    "CLARIFYING": "Need a little more detail…",
}


# --------------------------------------------------------------------------- #
# SSE client
# --------------------------------------------------------------------------- #
def _stream_events(message: str, history_pairs: list):
    """Yield decoded event dicts from the backend SSE stream.

    Any transport failure is turned into a single ``error`` event so the UI can
    show a friendly message instead of raising.
    """
    payload = {"message": message, "history": history_pairs}
    try:
        with httpx.stream(
            "POST", API_URL, json=payload, timeout=REQUEST_TIMEOUT
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line or not line.startswith("data: "):
                    continue
                try:
                    yield json.loads(line[6:])
                except json.JSONDecodeError:
                    continue
    except Exception:
        yield {
            "type": "error",
            "message": (
                "I can't reach the travel service right now. Please make sure the "
                "backend is running and try again."
            ),
        }


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
def _to_pairs(history: list) -> list:
    """Convert Gradio 'messages' history into [user, assistant] pairs."""
    pairs, pending = [], None
    for msg in history or []:
        role, content = msg.get("role"), msg.get("content", "")
        if role == "user":
            pending = content
        elif role == "assistant" and pending is not None:
            pairs.append([pending, content])
            pending = None
    return pairs


def _hotels_table(hotels: list) -> str:
    rows = ["| # | Hotel | City | Stars | Price/night | Rooms | ID |",
            "|---|-------|------|-------|-------------|-------|----|"]
    for i, h in enumerate(hotels[:MAX_TABLE_ROWS], 1):
        rows.append(
            f"| {i} | {h.get('name','—')} | {h.get('city','—')} | "
            f"{h.get('starRating','—')}★ | {h.get('currency','')} {h.get('pricePerNight','—')} | "
            f"{h.get('availableRooms','—')} | `{h.get('_id','')}` |"
        )
    table = "\n".join(rows)
    if len(hotels) > MAX_TABLE_ROWS:
        table += f"\n\n_…and {len(hotels) - MAX_TABLE_ROWS} more._"
    return table


def _flights_table(flights: list) -> str:
    rows = ["| # | Airline | Flight | Route | Date | Time | Price | Seats | ID |",
            "|---|---------|--------|-------|------|------|-------|-------|----|"]
    for i, f in enumerate(flights[:MAX_TABLE_ROWS], 1):
        origin = f.get("origin", {})
        dest = f.get("destination", {})
        o = origin.get("airport", origin) if isinstance(origin, dict) else origin
        d = dest.get("airport", dest) if isinstance(dest, dict) else dest
        rows.append(
            f"| {i} | {f.get('airline','—')} | {f.get('flightNumber','—')} | "
            f"{o}→{d} | {f.get('flightDate','—')} | "
            f"{f.get('departureTime','')}–{f.get('arrivalTime','')} | "
            f"{f.get('currency','')} {f.get('price','—')} | {f.get('availableSeats','—')} | "
            f"`{f.get('_id','')}` |"
        )
    table = "\n".join(rows)
    if len(flights) > MAX_TABLE_ROWS:
        table += f"\n\n_…and {len(flights) - MAX_TABLE_ROWS} more._"
    return table


def _compose_final(answer: str, result: dict) -> str:
    """Headline sentence + a rich table when structured results are present."""
    hotels = (result or {}).get("hotels") or []
    flights = (result or {}).get("flights") or []
    if hotels:
        headline = answer.splitlines()[0] if answer else "Here are some hotels:"
        return f"{headline}\n\n{_hotels_table(hotels)}"
    if flights:
        headline = answer.splitlines()[0] if answer else "Here are some flights:"
        return f"{headline}\n\n{_flights_table(flights)}"
    return answer


# --------------------------------------------------------------------------- #
# Chat handler (streaming generator)
# --------------------------------------------------------------------------- #
def respond(message: str, history: list):
    message = (message or "").strip()
    if not message:
        yield history or [], ""
        return

    history_pairs = _to_pairs(history)
    history = (history or []) + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": "_⏳ Understanding your request…_"},
    ]
    yield history, ""  # clear the input box immediately

    activity_label = ""
    answer = ""
    result = None
    error = None

    for event in _stream_events(message, history_pairs):
        etype = event.get("type")

        if etype == "activity":
            label = event.get("label") or ACTIVITY_FALLBACK.get(event.get("activity", ""), "")
            if label and not answer:
                activity_label = label
                history[-1]["content"] = f"_⏳ {label}_"
                yield history, ""

        elif etype == "token":
            answer += event.get("text", "")
            history[-1]["content"] = answer
            yield history, ""

        elif etype == "result":
            result = event

        elif etype == "error":
            error = event.get("message", "Something went wrong.")

        elif etype == "done":
            break

    if error and not answer:
        history[-1]["content"] = f"⚠️ {error}"
    else:
        history[-1]["content"] = _compose_final(answer, result) or "…"
    yield history, ""


# --------------------------------------------------------------------------- #
# UI
# --------------------------------------------------------------------------- #
THEME = gr.themes.Soft(primary_hue="teal", secondary_hue="orange")

CSS = """
.gradio-container { max-width: 900px !important; margin: auto !important; }
#tw-header { text-align: center; padding: 8px 0 4px; }
#tw-header h1 { margin-bottom: 2px; }
#tw-header p { color: var(--body-text-color-subdued); margin-top: 0; }
footer { visibility: hidden; }
"""


def build_demo():
    with gr.Blocks(title="TripWeaver") as demo:
        gr.HTML(
            """
            <div id="tw-header">
                <h1>✈️ TripWeaver 🏨</h1>
                <p>Your conversational travel planner — ask about destinations,
                search hotels & flights, and book, all in plain language.</p>
            </div>
            """
        )
        chatbot = gr.Chatbot(
            height=460,
            show_label=False,
            placeholder="Ask me to find hotels or flights, or for travel advice.",
        )
        with gr.Row():
            message = gr.Textbox(
                scale=8,
                show_label=False,
                placeholder="e.g. 'Find hotels in Bangkok' or 'flights from NRT to ICN'",
                autofocus=True,
            )
            send = gr.Button("Send", variant="primary", scale=1)
        with gr.Row():
            clear = gr.Button("🗑 Clear", scale=1)
        gr.Examples(
            examples=[
                "Find hotels in Bangkok",
                "Flights from NRT to ICN on 2025-11-15",
                "What's the best time to visit Japan?",
                "Show me all hotels",
            ],
            inputs=message,
            label="Try one of these",
        )

        send.click(respond, [message, chatbot], [chatbot, message])
        message.submit(respond, [message, chatbot], [chatbot, message])
        clear.click(lambda: ([], ""), None, [chatbot, message])

    return demo


if __name__ == "__main__":
    demo = build_demo()
    demo.launch(
        theme=THEME,
        css=CSS,
        server_name=os.environ.get("FRONTEND_HOST", "0.0.0.0"),
        server_port=int(os.environ.get("FRONTEND_PORT", "7860")),
    )
