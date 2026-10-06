"""Launch the Flask UI and FastAPI MCP service together for local development."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


def build_commands(port: int = 5000, mcp_port: int = 8000) -> dict[str, list[str]]:
    flask_cmd = [str(VENV_PYTHON), str(ROOT / "app" / "flask_app.py"), "--port", str(port)]
    mcp_cmd = [
        str(VENV_PYTHON),
        "-m",
        "uvicorn",
        "app.api.fastapi_mcp.server:app",
        "--host",
        "0.0.0.0",
        "--port",
        str(mcp_port),
    ]
    return {"flask": flask_cmd, "mcp": mcp_cmd}


def main() -> int:
    parser = argparse.ArgumentParser(description="Start the Flask + FastAPI MCP app stack.")
    parser.add_argument("--port", type=int, default=5000, help="Port for the Flask app.")
    parser.add_argument("--mcp-port", type=int, default=8000, help="Port for the FastAPI MCP API.")
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    commands = build_commands(port=args.port, mcp_port=args.mcp_port)
    processes = []
    try:
        processes.append(subprocess.Popen(commands["flask"], env=env, cwd=str(ROOT)))
        processes.append(subprocess.Popen(commands["mcp"], env=env, cwd=str(ROOT)))
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        for proc in processes:
            proc.terminate()
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
