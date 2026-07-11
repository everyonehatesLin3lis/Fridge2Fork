from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, TypeAdapter, ValidationError


SchemaT = TypeVar("SchemaT", bound=BaseModel)


def parse_json_response(raw_text: str, schema: type[SchemaT]) -> SchemaT:
    """Parse raw JSON text and validate it against a Pydantic schema."""
    payload = _load_json(raw_text)

    try:
        return schema.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Model response did not match the expected schema.") from exc


def parse_json_list_response(raw_text: str, item_schema: type[SchemaT]) -> list[SchemaT]:
    """Parse raw JSON text and validate it as a list of Pydantic models."""
    payload = _load_json(raw_text)

    try:
        return TypeAdapter(list[item_schema]).validate_python(payload)
    except ValidationError as exc:
        raise ValueError("Model response did not match the expected list schema.") from exc


def _load_json(raw_text: str) -> object:
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        start_candidates = [index for index in (raw_text.find("{"), raw_text.find("[")) if index >= 0]
        if not start_candidates:
            raise ValueError("Model response was not valid JSON.")
        start = min(start_candidates)
        end = max(raw_text.rfind("}"), raw_text.rfind("]"))
        if end <= start:
            raise ValueError("Model response was not valid JSON.")

    try:
        return json.loads(raw_text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError("Model response was not valid JSON.") from exc
