"""One-command launcher for FridgeAgent.

Run `run.bat` (Windows double-click) or `python run.py`. It automates the
entire startup chain so no other terminal commands are needed:

1. Installs/updates dependencies into the virtual environment when
   requirements.txt changed.
2. Reads .env (if present) to decide the model mode.
3. For local mode: starts Ollama if it is not running and pulls the model
   if it is missing.
4. Falls back to mock mode automatically when no model backend is available,
   so the app always starts.
5. Launches the Streamlit webapp and opens it in the browser.

Flags:
    --mock    force APP_MODE=mock (no model calls)
    --google  force APP_MODE=google (needs GOOGLE_API_KEY in .env)
    --local   force APP_MODE=local (needs Ollama)
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
VENV_PYTHON = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
REQUIREMENTS = PROJECT_ROOT / "requirements.txt"
REQUIREMENTS_STAMP = PROJECT_ROOT / ".venv" / ".requirements_hash"
OLLAMA_STARTUP_TIMEOUT_SECONDS = 60


def log(message: str) -> None:
    print(f"[FridgeAgent] {message}", flush=True)


def ensure_dependencies() -> None:
    """Install requirements into the venv only when requirements.txt changed."""
    current_hash = hashlib.sha256(REQUIREMENTS.read_bytes()).hexdigest()
    if REQUIREMENTS_STAMP.exists() and REQUIREMENTS_STAMP.read_text().strip() == current_hash:
        return
    log("Installing dependencies (first run or requirements changed)...")
    subprocess.run(
        [str(VENV_PYTHON), "-m", "pip", "install", "-r", str(REQUIREMENTS)],
        check=True,
        cwd=PROJECT_ROOT,
    )
    REQUIREMENTS_STAMP.write_text(current_hash)
    log("Dependencies ready.")


def load_env_file() -> None:
    """Load .env into the process environment without overriding existing vars."""
    try:
        from dotenv import load_dotenv

        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass


def resolve_app_mode() -> str:
    for flag, mode in (("--mock", "mock"), ("--google", "google"), ("--local", "local")):
        if flag in sys.argv:
            os.environ["APP_MODE"] = mode
            return mode
    return os.environ.get("APP_MODE", "local").lower()


def ollama_base_url() -> str:
    return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")


def ollama_is_up() -> bool:
    try:
        with urllib.request.urlopen(f"{ollama_base_url()}/api/tags", timeout=3) as response:
            return response.status == 200
    except OSError:
        return False


def ollama_has_model(model: str) -> bool:
    try:
        with urllib.request.urlopen(f"{ollama_base_url()}/api/tags", timeout=5) as response:
            tags = json.load(response)
        return any(entry.get("name") == model for entry in tags.get("models", []))
    except (OSError, ValueError):
        return False


def ensure_ollama(model: str) -> bool:
    """Make sure Ollama is running and the model is available. Returns success."""
    if not ollama_is_up():
        ollama_exe = shutil.which("ollama")
        if ollama_exe is None:
            log("Ollama is not installed (https://ollama.com/download).")
            return False
        log("Starting Ollama in the background...")
        subprocess.Popen(
            [ollama_exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        deadline = time.time() + OLLAMA_STARTUP_TIMEOUT_SECONDS
        while time.time() < deadline and not ollama_is_up():
            time.sleep(1)
        if not ollama_is_up():
            log("Ollama did not become reachable in time.")
            return False
        log("Ollama is running.")

    if not ollama_has_model(model):
        log(f"Model {model} is not downloaded yet. Pulling it now (one-time, several GB)...")
        pull = subprocess.run([shutil.which("ollama") or "ollama", "pull", model], cwd=PROJECT_ROOT)
        if pull.returncode != 0 or not ollama_has_model(model):
            log(f"Could not pull model {model}.")
            return False
        log(f"Model {model} is ready.")
    return True


def find_free_port(preferred: int = 8501) -> int:
    for port in [preferred, *range(preferred + 1, preferred + 20)]:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


def main() -> int:
    os.chdir(PROJECT_ROOT)
    ensure_dependencies()
    load_env_file()
    mode = resolve_app_mode()

    if mode == "local":
        # gemma4:e4b text generation works well locally, but its Ollama vision
        # path returns "no image" on this stack, so photo analysis uses a
        # dedicated vision model by default.
        os.environ.setdefault("VISION_MODEL_NAME", "llava:7b")
        model = os.environ.get("GEMMA_MODEL_NAME", "gemma4:e4b")
        if not ensure_ollama(model):
            if os.environ.get("GOOGLE_API_KEY"):
                log("Falling back to APP_MODE=google (GOOGLE_API_KEY found in .env).")
                mode = "google"
            else:
                log("Falling back to APP_MODE=mock so the app still starts.")
                log("Install Ollama or set GOOGLE_API_KEY in .env for real model output.")
                mode = "mock"
        if mode == "local":
            vision_model = os.environ["VISION_MODEL_NAME"]
            if vision_model != model and not ensure_ollama(vision_model):
                log(f"Vision model {vision_model} unavailable; photo analysis will use {model}.")
                os.environ["VISION_MODEL_NAME"] = model
        os.environ["APP_MODE"] = mode
    elif mode == "google" and not os.environ.get("GOOGLE_API_KEY"):
        log("APP_MODE=google but GOOGLE_API_KEY is missing in .env. Falling back to mock.")
        os.environ["APP_MODE"] = mode = "mock"
    else:
        os.environ["APP_MODE"] = mode

    if not (PROJECT_ROOT / "data" / "recipe_rag_index.jsonl").exists():
        log("Note: local recipe RAG index not found; recipes still work without it.")
        log("Build it later with scripts/download_recipe_dataset.py + scripts/build_recipe_rag_index.py.")

    port = find_free_port()
    log(f"Starting FridgeAgent webapp in APP_MODE={mode} on http://localhost:{port}")
    log("Press Ctrl+C (or close this window) to stop.")
    app = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "streamlit", "run", "main.py", "--server.port", str(port)],
        cwd=PROJECT_ROOT,
    )
    try:
        return app.wait()
    except KeyboardInterrupt:
        app.terminate()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
