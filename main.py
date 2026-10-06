"""Project-level launcher for the Flask UI and FastAPI MCP stack."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"


def build_commands(mode: str, flask_port: int, mcp_port: int) -> list[list[str]]:
    commands: list[list[str]] = []
    if mode in {"all", "flask"}:
        commands.append([str(VENV_PYTHON), str(ROOT / "app" / "flask_app.py"), "--port", str(flask_port)])
    if mode in {"all", "mcp"}:
        commands.append([
            str(VENV_PYTHON),
            "-m",
            "uvicorn",
            "app.api.fastapi_mcp.server:app",
            "--host",
            "0.0.0.0",
            "--port",
            str(mcp_port),
        ])
    return commands


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the refactored Job Application Assistant stack.")
    parser.add_argument("--mode", choices=["all", "flask", "mcp"], default="all")
    parser.add_argument("--flask-port", type=int, default=5000)
    parser.add_argument("--mcp-port", type=int, default=8000)
    args = parser.parse_args()

    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    processes: list[subprocess.Popen] = []
    try:
        for command in build_commands(args.mode, args.flask_port, args.mcp_port):
            processes.append(subprocess.Popen(command, cwd=str(ROOT), env=env))
        for proc in processes:
            proc.wait()
    except KeyboardInterrupt:
        for proc in processes:
            proc.terminate()
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
