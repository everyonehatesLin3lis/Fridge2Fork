from __future__ import annotations


def split_csv_items(value: str) -> list[str]:
    """Split comma-separated user input into clean item strings."""
    return [item.strip() for item in value.split(",") if item.strip()]
