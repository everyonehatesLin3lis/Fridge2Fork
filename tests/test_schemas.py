from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.ingredient_schema import Ingredient
from src.schemas.preference_schema import UserPreferences


def test_ingredient_confidence_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        Ingredient(name="eggs", category="protein", confidence=1.5)


def test_user_preferences_valid_example() -> None:
    prefs = UserPreferences(
        goal="high_protein",
        allergies=["peanuts"],
        max_cooking_time_minutes=25,
        meals_needed=2,
        gender="male",
        available_tools=["pan"],
    )
    assert prefs.goal == "high_protein"
    assert prefs.gender == "male"


def test_user_preferences_gender_values() -> None:
    for gender in ["male", "female", "none"]:
        prefs = UserPreferences(
            goal="healthy",
            allergies=[],
            max_cooking_time_minutes=30,
            meals_needed=1,
            gender=gender,
        )
        assert prefs.gender == gender
