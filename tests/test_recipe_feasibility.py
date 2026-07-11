from __future__ import annotations

from src.schemas.recipe_schema import IngredientAmount, RecipeCandidate
from src.utils.recipe_feasibility import classify_ingredient_roles, validate_and_repair_recipe


def test_classifies_soft_dairy_and_protein_roles() -> None:
    assert "wet_soft" in classify_ingredient_roles("cottage cheese")
    assert "wet_soft" in classify_ingredient_roles("high protein yogurt")
    assert "protein" in classify_ingredient_roles("deli meat")


def test_repairs_pie_skillet_without_binder_or_base() -> None:
    recipe = RecipeCandidate(
        title="Breakfast String Pie Skillet",
        time_minutes=15,
        portions=1,
        ingredients_used=["cottage cheese", "high protein yogurt", "deli meat", "philadelphia"],
        ingredient_amounts=[
            IngredientAmount(name="cottage cheese", amount_per_portion="150 g", total_amount="150 g"),
            IngredientAmount(name="high protein yogurt", amount_per_portion="120 g", total_amount="120 g"),
            IngredientAmount(name="deli meat", amount_per_portion="80 g", total_amount="80 g"),
            IngredientAmount(name="philadelphia", amount_per_portion="30 g", total_amount="30 g"),
        ],
        missing_ingredients=[],
        steps=[
            "Cut cottage cheese and yogurt into 1 cm pieces.",
            "Heat a pan on high heat and sear everything until crispy.",
        ],
        food_waste_note="Uses dairy.",
    )

    result = validate_and_repair_recipe(recipe)

    assert not result.valid
    assert "Protein Bowl" in result.repaired_recipe.title
    repaired_steps = " ".join(result.repaired_recipe.steps).lower()
    assert "do not sear or boil" in repaired_steps
    assert "cut cottage cheese" not in repaired_steps


def test_valid_egg_skillet_passes() -> None:
    recipe = RecipeCandidate(
        title="Breakfast Egg Spinach Skillet",
        time_minutes=15,
        portions=1,
        ingredients_used=["eggs", "spinach"],
        ingredient_amounts=[
            IngredientAmount(name="eggs", amount_per_portion="2 eggs", total_amount="2 eggs"),
            IngredientAmount(name="spinach", amount_per_portion="80 g", total_amount="80 g"),
        ],
        missing_ingredients=[],
        steps=[
            "Cook spinach over medium heat for 2 minutes.",
            "Add beaten eggs and cook over medium-low heat until set.",
        ],
        food_waste_note="Uses spinach.",
    )

    result = validate_and_repair_recipe(recipe)

    assert result.valid
    assert result.repaired_recipe.title == recipe.title
