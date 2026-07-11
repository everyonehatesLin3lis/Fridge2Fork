from __future__ import annotations

from pydantic import BaseModel

from src.schemas.recipe_schema import FinalRecipe, RankedRecipe, SafeRecipe


ALLERGEN_KEYWORDS = {
    "peanut": {"peanut", "peanuts", "peanut butter"},
    "peanuts": {"peanut", "peanuts", "peanut butter"},
    "dairy": {"milk", "cheese", "cheddar", "yogurt", "butter", "cream"},
    "gluten": {"wheat", "flour", "bread", "pasta", "soy sauce"},
    "egg": {"egg", "eggs"},
    "eggs": {"egg", "eggs"},
}


class FinalRecipeAgentResult(BaseModel):
    safe_recipes: list[SafeRecipe]
    final_recipes: list[FinalRecipe]


def run(ranked_recipes: list[RankedRecipe], allergies: list[str]) -> FinalRecipeAgentResult:
    """Filter unsafe recipes and turn safe recipes into final cards."""
    safe_recipes = filter_safe_recipes(ranked_recipes, allergies)
    final_recipes = [
        FinalRecipe(
            title=recipe.ranked_recipe.candidate.title,
            time_minutes=recipe.ranked_recipe.candidate.time_minutes,
            prep_time_minutes=recipe.ranked_recipe.candidate.prep_time_minutes,
            cook_time_minutes=recipe.ranked_recipe.candidate.cook_time_minutes,
            portions=recipe.ranked_recipe.candidate.portions,
            ingredients_used=recipe.ranked_recipe.candidate.ingredients_used,
            ingredient_amounts=recipe.ranked_recipe.candidate.ingredient_amounts,
            missing_ingredients=recipe.ranked_recipe.candidate.missing_ingredients,
            steps=recipe.ranked_recipe.candidate.steps,
            nutrition=recipe.ranked_recipe.nutrition,
            goal_fit=recipe.ranked_recipe.goal_fit,
            food_waste_note=recipe.ranked_recipe.candidate.food_waste_note,
            safety_warnings=recipe.safety_warnings,
        )
        for recipe in safe_recipes
    ]
    return FinalRecipeAgentResult(safe_recipes=safe_recipes, final_recipes=final_recipes)


def filter_safe_recipes(recipes: list[RankedRecipe], allergies: list[str]) -> list[SafeRecipe]:
    """Remove direct allergen conflicts and warn about hidden packaged allergens."""
    normalized_allergies = [allergy.lower().strip() for allergy in allergies]
    safe: list[SafeRecipe] = []

    for recipe in recipes:
        haystack = " ".join(
            [
                recipe.candidate.title,
                *recipe.candidate.ingredients_used,
                *recipe.candidate.missing_ingredients,
                *recipe.candidate.steps,
            ]
        ).lower()
        blocked = False
        warnings = []

        for allergy in normalized_allergies:
            keywords = ALLERGEN_KEYWORDS.get(allergy, {allergy})
            if any(keyword in haystack for keyword in keywords):
                blocked = True
                break
            if allergy in {"peanut", "peanuts", "dairy", "gluten", "egg", "eggs"}:
                warnings.append(f"Check packaged ingredients for hidden {allergy} before cooking.")

        if not blocked:
            safe.append(SafeRecipe(ranked_recipe=recipe, safety_warnings=warnings))

    return safe
