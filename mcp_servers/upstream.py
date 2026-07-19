"""HTTP helper the MCP servers use to reach the upstream travel service.

Base URL and timeout come from env. Failures are returned as a structured
error dict rather than raised, which is what lets the agents degrade gracefully.
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
    return {"error": True, "message": message, **extra}


def get_json(path: str, params: dict | None = None):
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
    url = f"{BASE_URL}{path}"
    try:
        response = httpx.post(url, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        return _error(
            f"The request was rejected by the travel service ({exc.response.status_code}).",
            status_code=exc.response.status_code,
            detail=exc.response.text,
        )
    except httpx.RequestError as exc:
        return _error(f"The travel service is unavailable right now: {exc}")
    except ValueError as exc:
        return _error(f"The travel service returned an invalid response: {exc}")
