from __future__ import annotations

import pytest

from src.schemas.ingredient_schema import Ingredient
from src.services.json_parser import parse_json_response


def test_parse_json_response_validates_schema() -> None:
    ingredient = parse_json_response(
        '{"name": "eggs", "category": "protein", "confidence": 0.9}',
        Ingredient,
    )
    assert ingredient.name == "eggs"


def test_parse_json_response_rejects_invalid_json() -> None:
    with pytest.raises(ValueError):
        parse_json_response("not json", Ingredient)
