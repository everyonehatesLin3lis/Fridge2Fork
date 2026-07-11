from __future__ import annotations

from src.agents.final_recipe_agent import filter_safe_recipes
from src.schemas.recipe_schema import NutritionEstimate, RankedRecipe, RecipeCandidate


def ranked_recipe(title: str, ingredients: list[str]) -> RankedRecipe:
    return RankedRecipe(
        candidate=RecipeCandidate(
            title=title,
            time_minutes=15,
            ingredients_used=ingredients,
            missing_ingredients=[],
            steps=["Cook everything until done."],
            food_waste_note="Uses food soon.",
        ),
        nutrition=NutritionEstimate(calories=300, protein_g=20, carbs_g=10, fat_g=12),
        goal_fit="Fits the goal.",
        rank_score=1,
    )


def test_filters_peanut_dairy_gluten_and_egg_allergies() -> None:
    recipes = [
        ranked_recipe("Peanut Noodles", ["peanut butter", "noodles"]),
        ranked_recipe("Cheese Eggs", ["cheddar cheese", "eggs"]),
        ranked_recipe("Tomato Bowl", ["tomatoes", "spinach"]),
    ]
    safe = filter_safe_recipes(recipes, ["peanuts", "dairy", "gluten", "egg"])
    assert [recipe.ranked_recipe.candidate.title for recipe in safe] == ["Tomato Bowl"]
    assert safe[0].safety_warnings
