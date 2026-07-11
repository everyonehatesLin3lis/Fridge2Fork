from __future__ import annotations

from pathlib import Path


def load_image_bytes(path: str | Path) -> bytes:
    """Load image bytes from disk."""
    return Path(path).read_bytes()
