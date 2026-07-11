from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.orchestrator import run_fridge_agent_workflow
from src.services.recipe_rag import RecipeRagStore


EIGHT_INGREDIENTS = [
    "chicken breast",
    "eggs",
    "cooked rice",
    "spinach",
    "tomatoes",
    "cheddar cheese",
    "Greek yogurt",
    "bell pepper",
]


SCENARIOS = [
    {
        "name": "high_protein_two_portions",
        "preferences": {
            "goal": "high_protein",
            "allergies": [],
            "diet_style": "normal",
            "max_cooking_time_minutes": 30,
            "meals_needed": 2,
            "meal_type": "dinner",
            "constraint_resolution": "make_best_effort",
            "height_cm": 180,
            "weight_kg": 82,
            "available_tools": ["pan", "oven"],
        },
    },
    {
        "name": "dairy_free_four_portions",
        "preferences": {
            "goal": "healthy",
            "allergies": ["dairy"],
            "diet_style": "dairy_free",
            "max_cooking_time_minutes": 45,
            "meals_needed": 4,
            "meal_type": "meal_prep",
            "constraint_resolution": "make_best_effort",
            "height_cm": 180,
            "weight_kg": 82,
            "available_tools": ["pan", "oven"],
        },
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run an 8-ingredient FridgeAgent debug comparison.")
    parser.add_argument("--app-mode", choices=["mock", "local", "live"], default=os.getenv("APP_MODE", "mock"))
    parser.add_argument("--output", default="data/sample_outputs/eight_ingredient_debug.json")
    args = parser.parse_args()

    os.environ["APP_MODE"] = args.app_mode
    output_path = ROOT / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "app_mode": args.app_mode,
        "recipe_rag_ready": RecipeRagStore().is_ready(),
        "ingredients": EIGHT_INGREDIENTS,
        "runs": [],
    }

    print(f"FridgeAgent 8-ingredient debug run | APP_MODE={args.app_mode}")
    print("Recipe RAG ready:", report["recipe_rag_ready"])
    print("Ingredients:", ", ".join(EIGHT_INGREDIENTS))

    for scenario in SCENARIOS:
        print(f"\n=== Scenario: {scenario['name']} ===")
        events: list[dict[str, Any]] = []

        def monitor(agent_name: str, message: str, details: dict[str, Any] | None = None) -> None:
            event = {
                "time": datetime.now().strftime("%H:%M:%S"),
                "agent": agent_name,
                "message": message,
                "details": details or {},
            }
            events.append(event)
            print(f"[{event['time']}] {agent_name}: {message}")
            reason = event["details"].get("reason_summary")
            if reason:
                print(f"  reason_summary: {reason}")

        raw_preferences = {
            **scenario["preferences"],
            "confirmed_ingredients": EIGHT_INGREDIENTS,
        }
        result = run_fridge_agent_workflow(
            image=None,
            raw_user_preferences=raw_preferences,
            monitor=monitor,
        )
        metrics = _metrics(result, raw_preferences)
        print("Metrics:", json.dumps(metrics, indent=2))

        report["runs"].append(
            {
                "scenario": scenario["name"],
                "preferences": raw_preferences,
                "metrics": metrics,
                "events": events,
                "result": result.model_dump(),
            }
        )

    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote debug report to {output_path}")


def _metrics(result: Any, raw_preferences: dict[str, Any]) -> dict[str, Any]:
    final_recipes = result.final_recipes
    blocked = [item.lower() for item in raw_preferences.get("allergies", [])]
    return {
        "hermes_stage_count": len(result.steps_run),
        "recipe_rag_ready": RecipeRagStore().is_ready(),
        "hermes_steps": result.steps_run,
        "monitorable_trace_entries": len(result.hermes_trace),
        "final_recipe_count": len(final_recipes),
        "average_cooking_detail_score": _average(
            [_cooking_detail_score(recipe.steps) for recipe in final_recipes]
        ),
        "portion_amount_coverage": _average(
            [
                len(recipe.ingredient_amounts) / max(len(recipe.ingredients_used), 1)
                for recipe in final_recipes
            ]
        ),
        "recipes_with_total_nutrition": sum(
            1
            for recipe in final_recipes
            if recipe.nutrition.calories_total is not None and recipe.nutrition.protein_total_g is not None
        ),
        "possible_allergy_bug": _contains_blocked_items(final_recipes, blocked),
        "titles": [recipe.title for recipe in final_recipes],
    }


def _cooking_detail_score(steps: list[str]) -> float:
    text = " ".join(steps).lower()
    checks = [
        any(word in text for word in ["medium", "high heat", "low heat", "oven", "air fryer"]),
        any(word in text for word in ["minute", "minutes"]),
        any(word in text for word in ["cm", "bite-size", "slice", "sliced", "whole", "pieces"]),
        any(word in text for word in ["stir", "flip", "cover", "uncover"]),
        any(word in text for word in ["ready", "tender", "set", "no pink", "juices run clear", "wilted"]),
    ]
    return round(sum(checks) / len(checks), 2)


def _contains_blocked_items(recipes: list[Any], blocked: list[str]) -> bool:
    if not blocked:
        return False
    haystack = json.dumps(
        [
            {
                "title": recipe.title,
                "ingredients_used": recipe.ingredients_used,
                "missing_ingredients": recipe.missing_ingredients,
                "steps": recipe.steps,
            }
            for recipe in recipes
        ]
    ).lower()
    return any(item and item in haystack for item in blocked)


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


if __name__ == "__main__":
    main()
