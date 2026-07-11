from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.schemas.preference_schema import UserPreferences


class ConstraintAgentResult(BaseModel):
    preferences: UserPreferences
    warnings: list[str]


def run(raw_preferences: dict[str, Any]) -> ConstraintAgentResult:
    """Validate user preferences and surface planning constraints."""
    preferences = UserPreferences.model_validate(raw_preferences)
    return ConstraintAgentResult(preferences=preferences, warnings=_constraint_warnings(preferences))


def _constraint_warnings(preferences: UserPreferences) -> list[str]:
    warnings = []
    if preferences.max_cooking_time_minutes <= 30 and preferences.meals_needed >= 8:
        warnings.append(
            "Many portions with a short cooking time may require meal prep, assembly-style recipes, or fewer servings."
        )
    if preferences.meal_type == "snack" and preferences.meals_needed >= 8:
        warnings.append("Snack portions are feasible, but the planner should avoid full-meal assumptions.")
    if preferences.max_cooking_time_minutes >= 240:
        warnings.append("Long cooking time is available, so slow cooking, roasting, or batch prep can be considered.")
    return warnings
