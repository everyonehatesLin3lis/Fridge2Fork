from __future__ import annotations

from src.agents.recipe_planner_agent import plan_recipes, rank_recipes
from src.schemas.ingredient_schema import Ingredient, VerifiedIngredients
from src.schemas.preference_schema import UserPreferences


def test_recipe_planner_includes_amount_for_each_used_ingredient() -> None:
    recipes = plan_recipes(
        ingredients=VerifiedIngredients(
            ingredients=[
                Ingredient(name="chicken breast", category="protein", confidence=1.0),
                Ingredient(name="rice", category="grain", confidence=1.0),
                Ingredient(name="spinach", category="vegetable", confidence=1.0),
            ],
        ),
        preferences=UserPreferences(
            goal="high_protein",
            allergies=[],
            max_cooking_time_minutes=60,
            meals_needed=3,
            available_tools=["pan"],
        ),
    )

    for recipe in recipes:
        amount_names = {amount.name for amount in recipe.ingredient_amounts}
        assert set(recipe.ingredients_used) <= amount_names
        assert recipe.portions == 3


def test_count_based_ingredients_include_approximate_measurement() -> None:
    recipes = plan_recipes(
        ingredients=VerifiedIngredients(
            ingredients=[
                Ingredient(name="eggs", category="protein", confidence=1.0),
                Ingredient(name="spinach", category="vegetable", confidence=1.0),
            ],
        ),
        preferences=UserPreferences(
            goal="quick",
            allergies=[],
            max_cooking_time_minutes=30,
            meals_needed=2,
            available_tools=["pan"],
        ),
    )

    egg_amount = next(
        amount
        for recipe in recipes
        for amount in recipe.ingredient_amounts
        if "egg" in amount.name
    )
    assert "50 g" in egg_amount.amount_per_portion
    assert "100 g" in egg_amount.total_amount


def test_multiline_ingredients_are_split_and_measured_separately() -> None:
    recipes = plan_recipes(
        ingredients=VerifiedIngredients(
            ingredients=[
                Ingredient(
                    name="pasta\nbacon\neggs\nparmesan cheese",
                    category="grain",
                    confidence=1.0,
                ),
            ],
        ),
        preferences=UserPreferences(
            goal="budget",
            allergies=[],
            max_cooking_time_minutes=30,
            meals_needed=6,
            available_tools=["pan", "pot"],
        ),
    )

    first_recipe = recipes[0]
    amounts = {amount.name: amount for amount in first_recipe.ingredient_amounts}

    assert {"pasta", "bacon", "eggs", "parmesan cheese"} <= set(first_recipe.ingredients_used)
    assert amounts["pasta"].total_amount == "450 g"
    assert amounts["bacon"].total_amount == "180 g"
    assert "300 g" in amounts["eggs"].total_amount
    assert amounts["parmesan cheese"].total_amount == "90 g"


def test_gender_changes_daily_calorie_context() -> None:
    recipes = plan_recipes(
        ingredients=VerifiedIngredients(
            ingredients=[Ingredient(name="eggs", category="protein", confidence=1.0)],
        ),
        preferences=UserPreferences(
            goal="healthy",
            allergies=[],
            max_cooking_time_minutes=30,
            meals_needed=1,
            available_tools=["pan"],
        ),
    )
    male_ranked = rank_recipes(
        recipes,
        UserPreferences(
            goal="healthy",
            allergies=[],
            max_cooking_time_minutes=30,
            meals_needed=1,
            gender="male",
            height_cm=180,
            weight_kg=80,
        ),
    )
    female_ranked = rank_recipes(
        recipes,
        UserPreferences(
            goal="healthy",
            allergies=[],
            max_cooking_time_minutes=30,
            meals_needed=1,
            gender="female",
            height_cm=180,
            weight_kg=80,
        ),
    )

    assert male_ranked[0].nutrition.estimated_daily_calorie_need != female_ranked[0].nutrition.estimated_daily_calorie_need


def test_recipe_planner_returns_no_recipes_without_ingredients() -> None:
    recipes = plan_recipes(
        ingredients=VerifiedIngredients(ingredients=[]),
        preferences=UserPreferences(
            goal="healthy",
            allergies=[],
            max_cooking_time_minutes=30,
            meals_needed=1,
        ),
    )

    assert recipes == []


def test_planner_repairs_wet_soft_skills_without_binder() -> None:
    recipes = plan_recipes(
        ingredients=VerifiedIngredients(
            ingredients=[
                Ingredient(name="cottage cheese", category="dairy", confidence=1.0),
                Ingredient(name="high protein yogurt", category="dairy", confidence=1.0),
                Ingredient(name="deli meat", category="protein", confidence=1.0),
                Ingredient(name="philadelphia", category="dairy", confidence=1.0),
            ],
        ),
        preferences=UserPreferences(
            goal="high_protein",
            allergies=[],
            max_cooking_time_minutes=30,
            meals_needed=1,
            available_tools=["pan"],
        ),
    )

    assert recipes
    assert all("pie" not in recipe.title.lower() for recipe in recipes)
    assert all("cut cottage cheese" not in " ".join(recipe.steps).lower() for recipe in recipes)
