from __future__ import annotations

from pathlib import Path

from src.schemas.preference_schema import UserPreferences
from src.services.recipe_rag import RecipeRagStore


def test_recipe_rag_search_returns_matching_reference(tmp_path: Path) -> None:
    index = tmp_path / "recipe_rag_index.jsonl"
    index.write_text(
        (
            '{"title": "Chicken Rice Bake", "ingredients": ["chicken breast", "cooked rice"], '
            '"directions": ["Bake at 350 degrees for 30 minutes."], "source": "test"}\n'
            '{"title": "Chocolate Cake", "ingredients": ["cocoa", "flour"], '
            '"directions": ["Bake cake."], "source": "test"}\n'
        ),
        encoding="utf-8",
    )

    results = RecipeRagStore(index).search(["chicken breast", "rice"], limit=1)

    assert results
    assert results[0].title == "Chicken Rice Bake"


def test_recipe_rag_does_not_search_without_ingredients(tmp_path: Path) -> None:
    index = tmp_path / "recipe_rag_index.jsonl"
    index.write_text(
        '{"title": "Egg Cake", "ingredients": ["egg"], "directions": ["Bake."], "source": "test"}\n',
        encoding="utf-8",
    )

    assert RecipeRagStore(index).search([], goal="high_protein", tools=["pan"]) == []


def test_user_preferences_allow_six_hour_cooking_window() -> None:
    prefs = UserPreferences(
        goal="healthy",
        allergies=[],
        max_cooking_time_minutes=360,
        meals_needed=6,
        available_tools=["oven"],
    )

    assert prefs.max_cooking_time_minutes == 360
