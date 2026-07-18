---
title: TripWeaver Multi Agent Travel Planner
emoji: ✈️
colorFrom: green
colorTo: orange
sdk: gradio
sdk_version: 6.20.0
app_file: app.py
pinned: false
---

# ✈️ TripWeaver — MCP-Based Multi-Agent Travel Planner

A conversational, multi-agent travel planner. A traveller chats in natural
language; a LangGraph graph routes their intent to one of three agents
(**General QA**, **Hotel**, **Flight**), which reach live hotel/flight services
**exclusively through MCP (Model Context Protocol) servers** and stream back a
coherent reply.

- **Live demo:** _add your Hugging Face Space URL here after first deploy_
- **Repository:** https://github.com/pramodkavi/TripWeaver-Multi-Agent-Travel-Planner

> The header block above is Hugging Face Space configuration; it is required for
> the Docker Space and is ignored elsewhere.

## Architecture

Four processes, one application:

```
┌─────────────┐   HTTP/SSE   ┌──────────────┐   MCP over HTTP   ┌──────────────────┐
│  Frontend   │ ───────────▶ │   Backend    │ ────────────────▶ │  MCP servers     │ ──▶ live travel
│  (Gradio)   │ ◀─────────── │ (FastAPI +   │ ◀──────────────── │  hotel  : 8001   │      service
│   :7860     │  event stream│  LangGraph)  │   tool results    │  flight : 8002   │
└─────────────┘              │   :8000      │                   └──────────────────┘
                             └──────────────┘
```

- **`agents/`** — the multi-agent brain: shared state (`entity.py`), intent
  router + Hotel/Flight/General agents (`nodes.py`), graph wiring (`graph.py`),
  the MCP client that discovers/calls tools (`mcp_client.py`), prompts, and the
  swappable LLM (`llm.py`).
- **`mcp_servers/`** — standalone FastMCP servers exposing `list/search/book`
  for hotels and flights; `upstream.py` is the *only* code that talks to the
  real travel API.
- **`main.py`** — FastAPI backend; streams the agent lifecycle over SSE.
- **`frontend.py`** — Gradio streaming chat UI.

See **[docs/MCP_SETUP.md](docs/MCP_SETUP.md)** for how the MCP layer works and
how to add/swap a service, and **[docs/USER_GUIDE.md](docs/USER_GUIDE.md)** for
how to use the chat.

## Features

- Intent-based routing (the traveller never names an agent).
- All external data reached **only through MCP tools** — swapping a provider
  needs no agent-code changes.
- Streaming responses with live agent-activity cues
  (`ROUTING → SEARCHING/BOOKING → RESPONDING`, `CLARIFYING`).
- Asks follow-up questions for missing inputs; never fabricates data.
- Graceful degradation — a failed/unavailable MCP service yields a friendly
  message and never crashes the app.
- Travel-themed, responsive UI with result tables.

## Local development

### Prerequisites
- Python 3.11+
- An OpenAI API key

### Setup
```bash
python -m venv env
# Windows (PowerShell): .\env\Scripts\Activate.ps1
# macOS/Linux:          source env/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then edit .env and set OPENAI_API_KEY
```

### Run (one command)
`app.py` starts all four processes (MCP servers + backend + UI):
```bash
python app.py
```
Open **http://localhost:7860**.

### Run (4 terminals, if you prefer them separate)
```bash
# 1) Hotel MCP server   (port 8001)
python -m mcp_servers.hotel_server
# 2) Flight MCP server  (port 8002)
python -m mcp_servers.flight_server
# 3) Backend API        (port 8000)
python main.py
# 4) Frontend UI        (port 7860)
python frontend.py
```
Sanity check: `curl http://localhost:8000/health`.

### Run with Docker (optional, other hosts)
A `Dockerfile` + `start.sh` are included for hosts that support Docker
(Hugging Face's free tier does not — see below):
```bash
docker build -t tripweaver .
docker run -p 7860:7860 -e OPENAI_API_KEY=sk-... tripweaver
```

## Deployment (Hugging Face Spaces + GitHub Actions)

Deployed as a free **Gradio Space** (Docker Spaces now require a paid plan). The
Space runs `app.py`, which launches the MCP servers + backend + Gradio UI as
separate processes. A GitHub Actions workflow mirrors the repo to the Space on
every push to `main`. Full steps: **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)**.

## Configuration (environment variables)

All configuration is via environment variables — nothing is hardcoded or
committed. See `.env.example` for the full list. Key ones:

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | LLM credentials (required) | — |
| `OPENAI_MODEL` | Chat model | `gpt-4o-mini` |
| `TRAVEL_SERVICE_BASE_URL` | Upstream travel API behind the MCP servers | Convex demo service |
| `HOTEL_MCP_URL` / `FLIGHT_MCP_URL` | MCP endpoints the backend connects to | `http://127.0.0.1:8001/mcp` / `:8002` |
| `HOTEL_MCP_PORT` / `FLIGHT_MCP_PORT` | Ports the MCP servers bind to | `8001` / `8002` |
| `BACKEND_HOST` / `BACKEND_PORT` | Backend bind address | `0.0.0.0` / `8000` |
| `CORS_ALLOW_ORIGINS` | Allowed CORS origins | `*` |
| `TRAVEL_PLANNER_API_URL` | Backend `/chat` URL the frontend calls | `http://127.0.0.1:8000/chat` |
| `FRONTEND_HOST` / `FRONTEND_PORT` | Frontend bind address | `0.0.0.0` / `7860` |

## Known limitations

- **Flight search uses IATA airport codes**, not city names (e.g. `NRT`→`ICN`,
  not `Tokyo`→`Seoul`). A city-name query honestly returns "no flights found".
- The upstream travel service is a shared demo backend; its data is fixed.

## Tech stack

Python · FastAPI · LangChain · LangGraph · MCP (FastMCP + langchain-mcp-adapters)
· Gradio · OpenAI.
