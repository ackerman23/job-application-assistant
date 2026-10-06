"""Cross-platform setup and launcher for the local Job Application Assistant."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
ENV_EXAMPLE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"


def venv_python() -> Path:
    executable = "python.exe" if os.name == "nt" else "python"
    return VENV / ("Scripts" if os.name == "nt" else "bin") / executable


def run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print(f"$ {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def install() -> None:
    if not VENV.exists():
        print(f"Creating virtual environment at {VENV}")
        run([sys.executable, "-m", "venv", str(VENV)])

    python = venv_python()
    if not python.exists():
        raise SystemExit(f"Could not find the virtual-environment Python executable at {python}")

    run([str(python), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python), "-m", "pip", "install", "-r", str(REQUIREMENTS)])

    if not ENV_FILE.exists():
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        print(f"Created {ENV_FILE}. Add OPENAI_API_KEY before using AI features.")
    else:
        print(f"Keeping existing {ENV_FILE}")

    print("Setup complete. Start the app with: python scripts/setup.py run")


def run_app(mode: str, flask_port: int, mcp_port: int) -> None:
    if not venv_python().exists():
        print("The virtual environment is missing; installing dependencies first.")
        install()

    command = [str(venv_python()), str(ROOT / "main.py"), "--mode", mode]
    command.extend(["--flask-port", str(flask_port), "--mcp-port", str(mcp_port)])
    run(command)


def run_tests() -> None:
    if not venv_python().exists():
        install()
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    run([str(venv_python()), "-m", "pytest", "-q"], env=env)


def clean() -> None:
    removed = 0
    for path in ROOT.rglob("__pycache__"):
        if path.is_dir() and ".venv" not in path.parts and ".git" not in path.parts and "data" not in path.parts:
            shutil.rmtree(path)
            removed += 1
    for path in (ROOT / ".pytest_cache", ROOT / ".ruff_cache"):
        if path.exists():
            shutil.rmtree(path)
            removed += 1
    print(f"Removed {removed} cache directories. Private profile and application data were preserved.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Set up and run the local Job Application Assistant.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("install", help="Create .venv, install dependencies, and create .env")
    run_parser = subparsers.add_parser("run", help="Start the application")
    run_parser.add_argument("--mode", choices=["all", "flask", "mcp"], default="all")
    run_parser.add_argument("--flask-port", type=int, default=5000)
    run_parser.add_argument("--mcp-port", type=int, default=8000)
    subparsers.add_parser("test", help="Run the test suite")
    subparsers.add_parser("clean", help="Remove generated Python/test caches without touching user data")
    args = parser.parse_args()

    if args.command == "install":
        install()
    elif args.command == "run":
        run_app(args.mode, args.flask_port, args.mcp_port)
    elif args.command == "test":
        run_tests()
    elif args.command == "clean":
        clean()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
