"""Single-process launcher — entry point for a Hugging Face Gradio Space.

A Gradio Space runs one file, but TripWeaver is four processes. This launcher
starts the two MCP servers and the FastAPI backend as background subprocesses,
waits for the backend to become ready, then runs the Gradio UI in the
foreground (the process the Space exposes on port 7860).

It also works locally as a one-command start:  ``python app.py``

The architecture is unchanged — these are still separate processes talking over
HTTP/MCP; only the orchestration differs from the multi-terminal workflow.
"""

import atexit
import os
import subprocess
import sys
import time
import urllib.request

from frontend import CSS, THEME, build_demo

_processes: list[subprocess.Popen] = []


def _spawn(*args: str) -> subprocess.Popen:
    """Start a child process (inherits env, incl. secrets like OPENAI_API_KEY)."""
    proc = subprocess.Popen([sys.executable, *args])
    _processes.append(proc)
    return proc


@atexit.register
def _shutdown() -> None:
    for proc in _processes:
        if proc.poll() is None:
            proc.terminate()


def _wait_for_backend(url: str = "http://127.0.0.1:8000/health", attempts: int = 60) -> None:
    for i in range(attempts):
        try:
            urllib.request.urlopen(url, timeout=2)
            print(f"Backend ready after {i + 1} attempt(s).", flush=True)
            return
        except Exception:
            time.sleep(1)
    print("Backend not confirmed ready; starting UI anyway (it degrades gracefully).", flush=True)


def main() -> None:
    print("Starting MCP servers and backend…", flush=True)
    _spawn("-m", "mcp_servers.hotel_server")
    _spawn("-m", "mcp_servers.flight_server")
    _spawn("main.py")

    _wait_for_backend()

    print("Launching Gradio UI…", flush=True)
    demo = build_demo()
    demo.launch(
        theme=THEME,
        css=CSS,
        server_name=os.environ.get("FRONTEND_HOST", "0.0.0.0"),
        server_port=int(os.environ.get("PORT", os.environ.get("FRONTEND_PORT", "7860"))),
        ssr_mode=False,
    )


if __name__ == "__main__":
    main()
