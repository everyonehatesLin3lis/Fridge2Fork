from __future__ import annotations


def format_list(items: list[str]) -> str:
    """Format a list for compact UI display."""
    return ", ".join(items) if items else "None"
