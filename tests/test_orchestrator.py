from __future__ import annotations

from src.orchestrator import run_fridge_agent_workflow


def test_orchestrator_runs_end_to_end() -> None:
    result = run_fridge_agent_workflow(
        image=None,
        raw_user_preferences={
            "goal": "high_protein",
            "allergies": [],
            "diet_style": "normal",
            "max_cooking_time_minutes": 25,
            "meals_needed": 2,
            "available_tools": ["pan"],
            "confirmed_ingredients": ["eggs", "spinach"],
        },
    )
    assert not result.detected_ingredients.ingredients
    assert result.verified_ingredients.ingredients
    assert result.recipe_candidates
    assert result.final_recipes
    assert result.steps_run == [
        "constraints",
        "recipe_planner",
        "final_recipe",
    ]
    assert len(result.hermes_trace) == 3


def test_orchestrator_runs_vision_only_when_image_uploaded() -> None:
    result = run_fridge_agent_workflow(
        image=b"fake image bytes",
        raw_user_preferences={
            "goal": "high_protein",
            "allergies": [],
            "diet_style": "normal",
            "max_cooking_time_minutes": 30,
            "meals_needed": 2,
            "available_tools": ["pan"],
            "confirmed_ingredients": ["rice"],
        },
    )

    assert result.steps_run == ["vision", "constraints", "recipe_planner", "final_recipe"]
    ingredient_names = {ingredient.name for ingredient in result.verified_ingredients.ingredients}
    assert "rice" in ingredient_names
    assert "eggs" not in ingredient_names


def test_orchestrator_accepts_multiple_uploaded_images() -> None:
    result = run_fridge_agent_workflow(
        image=[b"one", b"two"],
        raw_user_preferences={
            "goal": "healthy",
            "allergies": [],
            "diet_style": "normal",
            "max_cooking_time_minutes": 30,
            "meals_needed": 1,
            "available_tools": ["pan"],
            "confirmed_ingredients": ["rice"],
        },
    )

    assert result.steps_run == ["vision", "constraints", "recipe_planner", "final_recipe"]
    assert result.hermes_trace[0]["handoff_payload"]["input"] == "2 uploaded image(s)"


def test_orchestrator_splits_multiline_confirmed_ingredients() -> None:
    result = run_fridge_agent_workflow(
        image=None,
        raw_user_preferences={
            "goal": "budget",
            "allergies": [],
            "diet_style": "normal",
            "max_cooking_time_minutes": 30,
            "meals_needed": 6,
            "available_tools": ["pan", "pot"],
            "confirmed_ingredients": ["pasta\nbacon\neggs\nparmesan cheese"],
        },
    )

    ingredient_names = {ingredient.name for ingredient in result.verified_ingredients.ingredients}
    assert {"pasta", "bacon", "eggs", "parmesan cheese"} <= ingredient_names


def test_orchestrator_does_not_generate_recipes_without_verified_ingredients() -> None:
    result = run_fridge_agent_workflow(
        image=b"fake image bytes",
        raw_user_preferences={
            "goal": "high_protein",
            "allergies": ["peanuts", "dairy", "gluten"],
            "diet_style": "gluten_free",
            "max_cooking_time_minutes": 30,
            "meals_needed": 1,
            "gender": "female",
            "height_cm": 174,
            "weight_kg": 70,
            "available_tools": ["pan", "oven"],
        },
    )

    assert result.steps_run == ["vision", "constraints"]
    assert not result.verified_ingredients.ingredients
    assert not result.recipe_candidates
    assert not result.final_recipes
