# TripWeaver — MCP-Based Multi-Agent Travel Planner

A conversational multi-agent travel planner. A traveller chats in natural
language; a LangGraph graph routes their intent to one of three agents
(General QA, Hotel, Flight), which reach live hotel/flight services
**exclusively through MCP (Model Context Protocol) servers** and compose a
streamed reply.

> Status: **scaffold** (Phase 0 complete). Implementation lands over Phases 1–6.

## Architecture

Three processes make up one application:

1. **Backend** (`main.py`) — FastAPI endpoints fronting a LangGraph `StateGraph`.
2. **Frontend** (`frontend.py`) — Gradio streaming chat UI.
3. **MCP servers** (`mcp_servers/`) — standalone processes; the single point of
   contact with external travel services.

```
TripWeaver-Multi-Agent-Travel-Planner/
├─ agents/            # graph, nodes, state schema, prompts, LLM, MCP client
├─ mcp_servers/       # hotel & flight MCP servers (FastMCP, streamable-http)
├─ main.py            # FastAPI backend
├─ frontend.py        # Gradio frontend
├─ requirements.txt
└─ .env.example       # copy to .env and fill in
```

## Setup

```bash
python -m venv env
# Windows (PowerShell): env\Scripts\Activate.ps1
# macOS/Linux:          source env/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit .env
```

## Running

Detailed run instructions (MCP servers, backend, frontend) will be documented
as each phase lands. See `.env.example` for all configuration.

## Design constraints (from the SRS)

- MCP is the **only** bridge to external services — no third-party API logic in
  agent nodes; swapping a service must not touch agent code.
- The graph **routes by intent**; the traveller never names an agent.
- All inter-agent communication flows through the shared state schema.
- **No fabrication** — every hotel/flight fact comes from an MCP result.
- Missing inputs → ask a follow-up question, never guess.
- One failing MCP service must degrade gracefully, never crash the app.
- Stream responses with visible agent-activity cues.
- All config via environment variables.
