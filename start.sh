#!/usr/bin/env bash
# Launch all four TripWeaver processes inside one container.
#
# The MCP servers and backend run in the background on localhost; the Gradio UI
# runs in the foreground on the public port (7860). Because everything shares
# localhost here, the default env values already wire the pieces together:
#   backend  -> HOTEL_MCP_URL / FLIGHT_MCP_URL  (127.0.0.1:8001 / 8002)
#   frontend -> TRAVEL_PLANNER_API_URL          (127.0.0.1:8000/chat)
#
# Only OPENAI_API_KEY needs to be provided (as a Space secret).

set -euo pipefail

echo "Starting hotel MCP server (:8001)…"
python -m mcp_servers.hotel_server &

echo "Starting flight MCP server (:8002)…"
python -m mcp_servers.flight_server &

echo "Starting backend API (:8000)…"
python main.py &

echo "Waiting for the backend to become ready…"
python - <<'PY'
import time
import urllib.request

for attempt in range(40):
    try:
        urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2)
        print(f"Backend ready after {attempt + 1} attempt(s).")
        break
    except Exception:
        time.sleep(1)
else:
    print("Backend not confirmed ready; starting UI anyway (it will degrade gracefully).")
PY

echo "Starting Gradio UI (:7860)…"
exec python frontend.py
