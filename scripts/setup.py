"""Cross-platform setup and launcher for the local Job Application Assistant."""

from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
REQUIREMENTS = ROOT / "requirements.txt"
ENV_EXAMPLE = ROOT / ".env.example"
ENV_FILE = ROOT / ".env"
PROFILE_TEMPLATE = ROOT / "base-cv" / "candidate_profile.example.json"
PROFILE_FILE = ROOT / "data" / "candidate_profile.json"
SETTINGS_TEMPLATE = ROOT / "config" / "user-settings.example.yaml"
SETTINGS_FILE = ROOT / "config" / "user-settings.yaml"


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

    if not SETTINGS_FILE.exists():
        shutil.copyfile(SETTINGS_TEMPLATE, SETTINGS_FILE)
        print(f"Created {SETTINGS_FILE}. Edit it to personalize CV and cover-letter preferences.")
    else:
        print(f"Keeping existing {SETTINGS_FILE}")

    print("Setup complete. Start the app with: python scripts/setup.py run")


def env_has_openai_key() -> bool:
    if not ENV_FILE.exists():
        return False
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip() == "OPENAI_API_KEY":
            return bool(value.strip())
    return False


def port_is_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def validate_startup(mode: str, flask_port: int, mcp_port: int) -> None:
    ports = [("Flask dashboard", flask_port)] if mode == "flask" else [("FastAPI service", mcp_port)]
    if mode == "all":
        ports = [("Flask dashboard", flask_port), ("FastAPI service", mcp_port)]
    unavailable = [f"{name} port {port}" for name, port in ports if not port_is_available(port)]
    if unavailable:
        raise SystemExit(
            "Cannot start because "
            + " and ".join(unavailable)
            + " is already in use. Stop the other process or choose a different port with --flask-port or --mcp-port."
        )

    if not ENV_FILE.exists():
        print("Warning: .env is missing. Run 'python scripts/setup.py install' to create it.")
    elif not env_has_openai_key():
        print("Warning: OPENAI_API_KEY is not set. The dashboard will start, but job analysis and tailored cover letters need an API key.")

    if not shutil.which("latexmk") and not shutil.which("pdflatex"):
        print("Note: latexmk or pdflatex was not found. LaTeX downloads work, but PDF exports require a LaTeX installation.")


def run_app(mode: str, flask_port: int, mcp_port: int) -> None:
    if not venv_python().exists():
        print("The virtual environment is missing; installing dependencies first.")
        install()

    validate_startup(mode, flask_port, mcp_port)
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


def init_profile(force: bool) -> None:
    if PROFILE_FILE.exists() and not force:
        raise SystemExit(
            f"Profile already exists at {PROFILE_FILE}. Edit it in the dashboard, or use --force to replace it deliberately."
        )
    PROFILE_FILE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PROFILE_TEMPLATE, PROFILE_FILE)
    print(f"Created private profile from the fictional starter at {PROFILE_FILE}. Replace all example information before use.")


def init_settings(force: bool) -> None:
    if SETTINGS_FILE.exists() and not force:
        raise SystemExit(f"Settings already exist at {SETTINGS_FILE}. Edit them there, or use --force to replace them deliberately.")
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SETTINGS_TEMPLATE, SETTINGS_FILE)
    print(f"Created private settings from {SETTINGS_TEMPLATE} at {SETTINGS_FILE}.")


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
    profile_parser = subparsers.add_parser("init-profile", help="Copy the fictional base-CV profile into private local data")
    profile_parser.add_argument("--force", action="store_true", help="Replace an existing private profile")
    settings_parser = subparsers.add_parser("init-settings", help="Copy the user-settings template into private local configuration")
    settings_parser.add_argument("--force", action="store_true", help="Replace existing private settings")
    args = parser.parse_args()

    if args.command == "install":
        install()
    elif args.command == "run":
        run_app(args.mode, args.flask_port, args.mcp_port)
    elif args.command == "test":
        run_tests()
    elif args.command == "clean":
        clean()
    elif args.command == "init-profile":
        init_profile(args.force)
    elif args.command == "init-settings":
        init_settings(args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
