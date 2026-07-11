from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.recipe_rag import DEFAULT_INDEX_PATH


TITLE_KEYS = ("title", "name", "recipe_name", "recipe")
INGREDIENT_KEYS = ("ingredients", "ingredient", "ner", "cleaned_ingredients")
DIRECTION_KEYS = ("directions", "instructions", "steps", "method")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a small local recipe RAG index from the Kaggle dataset.")
    parser.add_argument("--dataset-path", required=True, help="Path returned by kagglehub.dataset_download")
    parser.add_argument("--output", default=str(DEFAULT_INDEX_PATH))
    parser.add_argument("--limit", type=int, default=25000)
    args = parser.parse_args()

    dataset_path = Path(args.dataset_path)
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with output_path.open("w", encoding="utf-8") as output:
        for file_path in _candidate_files(dataset_path):
            for record in _iter_records(file_path):
                normalized = _normalize_record(record, file_path.name)
                if not normalized:
                    continue
                output.write(json.dumps(normalized, ensure_ascii=True) + "\n")
                written += 1
                if written >= args.limit:
                    print(f"Wrote {written} recipe references to {output_path}")
                    return

    print(f"Wrote {written} recipe references to {output_path}")


def _candidate_files(dataset_path: Path) -> list[Path]:
    if dataset_path.is_file():
        return [dataset_path]
    return sorted(
        [
            path
            for path in dataset_path.rglob("*")
            if path.suffix.lower() in {".csv", ".json", ".jsonl"}
        ],
        key=lambda path: path.stat().st_size,
        reverse=True,
    )


def _iter_records(file_path: Path) -> Any:
    suffix = file_path.suffix.lower()
    if suffix == ".csv":
        with file_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                yield row
        return

    if suffix == ".jsonl":
        with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)
        return

    with file_path.open("r", encoding="utf-8", errors="ignore") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        yield from payload
    elif isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                yield from value
                return
        yield payload


def _normalize_record(record: dict[str, Any], source: str) -> dict[str, Any] | None:
    lower = {str(key).lower(): value for key, value in record.items()}
    title = _first_value(lower, TITLE_KEYS)
    ingredients = _first_value(lower, INGREDIENT_KEYS)
    directions = _first_value(lower, DIRECTION_KEYS)
    if not title or not ingredients or not directions:
        return None
    ingredient_list = _coerce_list(ingredients)
    direction_list = _coerce_list(directions)
    if len(ingredient_list) < 2 or not direction_list:
        return None
    return {
        "title": str(title).strip(),
        "ingredients": ingredient_list[:30],
        "directions": direction_list[:20],
        "source": source,
    }


def _first_value(record: dict[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in record and record[key]:
            return record[key]
    return None


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return [str(item).strip() for item in parsed if str(item).strip()]
    except json.JSONDecodeError:
        pass
    separators = ["\n", "|", ";"]
    for separator in separators:
        if separator in text:
            return [item.strip(" -") for item in text.split(separator) if item.strip(" -")]
    return [text]


if __name__ == "__main__":
    main()
