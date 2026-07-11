from __future__ import annotations

import re
from typing import Any, Callable

from src.agents import constraints_agent, final_recipe_agent, recipe_planner_agent, vision_agent
from src.orchestration import HermesOrchestrator
from src.schemas.agent_state_schema import AgentWorkflowState
from src.schemas.ingredient_schema import IngredientExtractionResponse, VerifiedIngredients
from src.services.recipe_rag import RecipeRagStore


MonitorCallback = Callable[[str, str, dict[str, Any] | None], None]


def run_fridge_agent_workflow(
    image: Any,
    raw_user_preferences: dict[str, Any],
    monitor: MonitorCallback | None = None,
) -> AgentWorkflowState:
    """Run the complete four-agent fridge-to-recipe workflow."""
    hermes = HermesOrchestrator()

    confirmed_ingredients = _normalize_confirmed_ingredients(
        raw_user_preferences.get("confirmed_ingredients", [])
    )
    images = _normalize_images(image)
    if images:
        hermes.prepare_handoff(
            "vision",
            {
                "input": f"{len(images)} uploaded image(s)",
                "confirmed_ingredients": confirmed_ingredients,
            },
            "Run detection, normalization, and verification once; keep uncertainty out of confirmed planning.",
        )
        _emit(
            monitor,
            "Vision Agent",
            f"Detecting, normalizing, merging, and verifying visible ingredients from {len(images)} image(s).",
            {"input": f"{len(images)} uploaded image(s)"},
        )
        vision_result = vision_agent.run(image=images, confirmed_ingredients=confirmed_ingredients)
        detected_ingredients = vision_result.detected_ingredients
        verified_ingredients = vision_result.verified_ingredients
        if confirmed_ingredients:
            _emit(
                monitor,
                "Vision Agent",
                "Merging typed confirmed ingredients with high-confidence photo detections.",
                {"confirmed_ingredients": confirmed_ingredients},
            )
        _emit(
            monitor,
            "Vision Agent",
            "Confirmed ingredients: "
            + ", ".join(ingredient.name for ingredient in verified_ingredients.ingredients),
            {
                "detected_output": detected_ingredients.model_dump(),
                "per_image_outputs": [
                    result.model_dump()
                    for result in vision_result.image_results
                ],
                "verified_output": verified_ingredients.model_dump(),
                "low_confidence_items_requiring_confirmation": vision_result.low_confidence_items,
                "reason_summary": "This agent only runs when images are uploaded; it merges detections across up to 5 photos and combines typed confirmations with high-confidence detections.",
            },
        )
    else:
        detected_ingredients = IngredientExtractionResponse(ingredients=[], uncertain_items=[])
        verified_ingredients = VerifiedIngredients(
            ingredients=[
                vision_agent.ingredient_from_confirmed_name(name)
                for name in confirmed_ingredients
            ],
            clarification_questions=[],
        )
        _emit(
            monitor,
            "Ingredient Input",
            "No image uploaded, so Vision Agent was skipped and typed ingredients were used directly.",
            {
                "verified_output": verified_ingredients.model_dump(),
                "reason_summary": "Skipping vision avoids unnecessary model calls when the user already typed confirmed ingredients.",
            },
        )

    hermes.prepare_handoff(
        "constraints",
        {
            "verified_ingredients": verified_ingredients.model_dump(),
            "raw_user_preferences": raw_user_preferences,
        },
        "Validate preferences, portions, allergies, time, and tools before planning.",
    )
    _emit(
        monitor,
        "Constraints Agent",
        "Validating cooking goals, allergies, portions, time, and tools.",
        {"input": raw_user_preferences},
    )
    constraint_result = constraints_agent.run(raw_user_preferences)
    normalized_preferences = constraint_result.preferences
    constraint_warnings = constraint_result.warnings
    _emit(
        monitor,
        "Constraints Agent",
        f"Goal is {normalized_preferences.goal}.",
        {
            "output": normalized_preferences.model_dump(),
            "constraint_warnings": constraint_warnings,
            "reason_summary": "Serving count, cooking time, allergies, and available tools are checked before planning.",
        },
    )

    if not verified_ingredients.ingredients:
        _emit(
            monitor,
            "Hermes",
            "Recipe generation stopped because there are no verified ingredients.",
            {
                "reason_summary": "Hermes will not let the planner invent ingredients. Upload a real image in APP_MODE=local or type confirmed ingredients.",
                "clarification_questions": verified_ingredients.clarification_questions,
            },
        )
        return AgentWorkflowState(
            detected_ingredients=detected_ingredients,
            verified_ingredients=verified_ingredients,
            preferences=normalized_preferences,
            recipe_candidates=[],
            ranked_recipes=[],
            safe_recipes=[],
            final_recipes=[],
            steps_run=hermes.steps_run,
            hermes_trace=hermes.trace_dump(),
        )

    recipe_references = RecipeRagStore().search(
        ingredients=[ingredient.name for ingredient in verified_ingredients.ingredients],
        goal=normalized_preferences.goal,
        tools=normalized_preferences.available_tools,
        limit=3,
    )
    retrieved_reference_dump = [
        {
            "title": reference.title,
            "score": reference.score,
            "source": reference.source,
            "ingredients": reference.ingredients[:8],
            "directions": reference.directions[:3],
        }
        for reference in recipe_references
    ]
    hermes.prepare_handoff(
        "recipe_planner",
        {
            "verified_ingredients": verified_ingredients.model_dump(),
            "preferences": normalized_preferences.model_dump(),
            "constraint_warnings": constraint_warnings,
            "retrieved_recipe_references": retrieved_reference_dump,
        },
        "Plan recipes, calculate portions, retrieve RAG references, and rank rough nutrition.",
    )
    _emit(
        monitor,
        "Recipe Planner Agent",
        "Generating recipe candidates with RAG references, portion math, cooking details, and rough nutrition.",
        {
            "input": {
                "ingredients": verified_ingredients.model_dump(),
                "preferences": normalized_preferences.model_dump(),
                "constraint_warnings": constraint_warnings,
                "retrieved_recipe_references": retrieved_reference_dump,
            }
        },
    )
    recipe_candidates, ranked_recipes = recipe_planner_agent.run(
        ingredients=verified_ingredients,
        preferences=normalized_preferences,
    )
    _emit(
        monitor,
        "Recipe Planner Agent",
        f"Created {len(recipe_candidates)} candidates and ranked {len(ranked_recipes)} recipes.",
        {
            "recipe_candidates": [recipe.model_dump() for recipe in recipe_candidates],
            "ranked_recipes": [recipe.model_dump() for recipe in ranked_recipes],
            "reason_summary": "This single agent handles RAG-grounded planning, portion calculations, cooking specificity, and rough nutrition ranking.",
        },
    )

    hermes.prepare_handoff(
        "final_recipe",
        {
            "ranked_recipes": [recipe.model_dump() for recipe in ranked_recipes],
            "allergies": normalized_preferences.allergies,
        },
        "Apply allergy safety and write final cards.",
    )
    _emit(
        monitor,
        "Final Recipe Agent",
        "Filtering allergens and writing final recipe cards.",
        {"input_allergies": normalized_preferences.allergies},
    )
    final_result = final_recipe_agent.run(
        ranked_recipes=ranked_recipes,
        allergies=normalized_preferences.allergies,
    )
    _emit(
        monitor,
        "Final Recipe Agent",
        f"Prepared {len(final_result.final_recipes)} final recipe cards.",
        {
            "safe_recipes": [recipe.model_dump() for recipe in final_result.safe_recipes],
            "final_recipes": [recipe.model_dump() for recipe in final_result.final_recipes],
            "reason_summary": "This single agent removes direct allergen conflicts, adds safety warnings, and formats final user-facing recipe cards.",
        },
    )

    return AgentWorkflowState(
        detected_ingredients=detected_ingredients,
        verified_ingredients=verified_ingredients,
        preferences=normalized_preferences,
        recipe_candidates=recipe_candidates,
        ranked_recipes=ranked_recipes,
        safe_recipes=final_result.safe_recipes,
        final_recipes=final_result.final_recipes,
        steps_run=hermes.steps_run,
        hermes_trace=hermes.trace_dump(),
    )


def _emit(
    monitor: MonitorCallback | None,
    agent_name: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    if monitor:
        monitor(agent_name, message, details)


def _normalize_confirmed_ingredients(raw_items: Any) -> list[str]:
    """Accept comma, semicolon, or newline separated ingredients from the UI."""
    if isinstance(raw_items, str):
        candidates = [raw_items]
    else:
        candidates = [str(item) for item in raw_items or []]

    normalized: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        for item in re.split(r"[,;\r\n]+", candidate):
            cleaned = item.strip(" -\t").lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
    return normalized


def _normalize_images(image: Any) -> list[Any]:
    if image is None:
        return []
    if isinstance(image, list):
        return image[:5]
    if isinstance(image, tuple):
        return list(image[:5])
    return [image]
