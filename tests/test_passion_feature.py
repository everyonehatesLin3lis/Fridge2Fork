from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.agents import constraints_agent, final_recipe_agent, recipe_planner_agent
from src.schemas.ingredient_schema import Ingredient, VerifiedIngredients
from src.schemas.preference_schema import UserPreferences
from src.schemas.recipe_schema import NutritionEstimate, RankedRecipe, RecipeCandidate


def _preferences(**overrides) -> UserPreferences:
    base = dict(
        goal="comfort_food",
        allergies=[],
        max_cooking_time_minutes=60,
        meals_needed=2,
        available_tools=["pan"],
    )
    base.update(overrides)
    return UserPreferences(**base)


def test_user_preferences_passion_note_optional() -> None:
    prefs = _preferences()
    assert prefs.passion_note is None


def test_user_preferences_passion_note_too_long_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _preferences(passion_note="x" * 281)


def test_constraints_agent_trims_passion_note() -> None:
    result = constraints_agent.run(
        {
            "goal": "comfort_food",
            "allergies": [],
            "max_cooking_time_minutes": 60,
            "meals_needed": 2,
            "available_tools": ["pan"],
            "passion_note": "  my grandmother's game-day chili  ",
        }
    )
    assert result.preferences.passion_note == "my grandmother's game-day chili"


def test_constraints_agent_blank_passion_note_becomes_none() -> None:
    result = constraints_agent.run(
        {
            "goal": "comfort_food",
            "allergies": [],
            "max_cooking_time_minutes": 60,
            "meals_needed": 2,
            "available_tools": ["pan"],
            "passion_note": "   ",
        }
    )
    assert result.preferences.passion_note is None


def test_recipe_planner_run_adds_passion_line_when_note_present() -> None:
    ingredients = VerifiedIngredients(
        ingredients=[
            Ingredient(name="chicken", category="protein", confidence=1.0),
            Ingredient(name="rice", category="grain", confidence=1.0),
        ],
    )
    preferences = _preferences(passion_note="my team's match-day chicken and rice")

    recipe_candidates, ranked_recipes = recipe_planner_agent.run(ingredients, preferences)

    assert recipe_candidates, "expected at least one recipe candidate"
    for recipe in recipe_candidates:
        assert recipe.passion_line
        assert "match-day chicken and rice" in recipe.passion_line
    for ranked in ranked_recipes:
        assert ranked.candidate.passion_line


def test_recipe_planner_run_has_no_passion_line_when_note_absent() -> None:
    ingredients = VerifiedIngredients(
        ingredients=[Ingredient(name="chicken", category="protein", confidence=1.0)],
    )
    preferences = _preferences()

    recipe_candidates, _ = recipe_planner_agent.run(ingredients, preferences)

    assert recipe_candidates
    assert all(recipe.passion_line is None for recipe in recipe_candidates)


def test_final_recipe_agent_copies_passion_line_onto_final_card() -> None:
    ranked = RankedRecipe(
        candidate=RecipeCandidate(
            title="Rivalry Night Chili",
            time_minutes=30,
            ingredients_used=["beans", "tomato"],
            missing_ingredients=[],
            steps=["Simmer everything together."],
            food_waste_note="Uses beans before they expire.",
            passion_line="Inspired by your passion for game day, this chili brings the fire.",
        ),
        nutrition=NutritionEstimate(calories=300, protein_g=15, carbs_g=30, fat_g=8),
        goal_fit="Fits the goal.",
        rank_score=1,
    )

    result = final_recipe_agent.run(ranked_recipes=[ranked], allergies=[])

    assert result.final_recipes[0].passion_line == ranked.candidate.passion_line
