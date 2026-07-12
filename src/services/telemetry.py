from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_TELEMETRY_DIR = Path("data/telemetry")


def telemetry_dir() -> Path:
    """Telemetry output directory, overridable with TELEMETRY_DIR for tests and CI."""
    return Path(os.getenv("TELEMETRY_DIR", str(DEFAULT_TELEMETRY_DIR)))


def log_event(kind: str, payload: dict[str, Any]) -> None:
    """Append one telemetry event to data/telemetry/<kind>.jsonl.

    Telemetry must never break the app, so all filesystem errors are swallowed.
    """
    try:
        directory = telemetry_dir()
        directory.mkdir(parents=True, exist_ok=True)
        record = {"timestamp": datetime.now(timezone.utc).isoformat(), **payload}
        with (directory / f"{kind}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError):
        pass


def read_events(kind: str) -> list[dict[str, Any]]:
    """Read all telemetry events of one kind. Returns [] when nothing was logged yet."""
    path = telemetry_dir() / f"{kind}.jsonl"
    if not path.exists():
        return []
    events = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


class Stopwatch:
    """Small perf_counter stopwatch for latency telemetry."""

    def __enter__(self) -> "Stopwatch":
        self._start = time.perf_counter()
        self.elapsed_ms = 0.0
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.elapsed_ms = round((time.perf_counter() - self._start) * 1000, 1)
