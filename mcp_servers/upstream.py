"""Shared upstream HTTP helper for the MCP servers.

The MCP servers are the *only* bridge between the agents and the external
travel service. This module centralises how that external service is reached:
base URL from env, sane timeouts, and — critically — every failure is turned
into a structured error dict (never a raised exception across the tool
boundary) so agents can degrade gracefully (SRS E3).
"""

import os

import httpx
from dotenv import load_dotenv

load_dotenv(override=True)

BASE_URL = os.getenv(
    "TRAVEL_SERVICE_BASE_URL", "https://standing-fish-574.convex.site"
).rstrip("/")

TIMEOUT = float(os.getenv("TRAVEL_SERVICE_TIMEOUT", "20"))


def _error(message: str, **extra) -> dict:
    """Build a structured error payload the agents can detect via ``error``."""
    return {"error": True, "message": message, **extra}


def get_json(path: str, params: dict | None = None):
    """GET ``{BASE_URL}{path}`` and return parsed JSON, or a structured error."""
    url = f"{BASE_URL}{path}"
    try:
        response = httpx.get(url, params=params, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return _error(
            f"The travel service returned an error ({exc.response.status_code}).",
            status_code=exc.response.status_code,
        )
    except httpx.RequestError as exc:
        return _error(f"The travel service is unavailable right now: {exc}")
    except ValueError as exc:
        return _error(f"The travel service returned an invalid response: {exc}")


def post_json(path: str, payload: dict):
    """POST ``payload`` to ``{BASE_URL}{path}`` and return JSON, or an error."""
    url = f"{BASE_URL}{path}"
    try:
        response = httpx.post(url, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        detail = ""
        try:
            detail = exc.response.text
        except Exception:  # pragma: no cover - best-effort detail only
            pass
        return _error(
            f"The request was rejected by the travel service ({exc.response.status_code}).",
            status_code=exc.response.status_code,
            detail=detail,
        )
    except httpx.RequestError as exc:
        return _error(f"The travel service is unavailable right now: {exc}")
    except ValueError as exc:
        return _error(f"The travel service returned an invalid response: {exc}")
