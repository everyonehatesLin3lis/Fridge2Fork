from __future__ import annotations

from dataclasses import dataclass

from src.schemas.recipe_schema import RecipeCandidate


WET_SOFT_TERMS = {
    "yogurt",
    "cottage cheese",
    "cream cheese",
    "philadelphia",
    "sour cream",
    "milk",
    "cream",
    "sauce",
}
BINDER_TERMS = {"egg", "eggs", "flour", "potato", "potatoes", "cheddar", "mozzarella", "parmesan"}
BASE_TERMS = {"tortilla", "wrap", "lavash", "bread", "pita", "rice", "pasta", "potato", "potatoes", "pastry"}
PROTEIN_TERMS = {"ham", "turkey", "chicken", "beef", "pork", "bacon", "tofu", "fish", "deli meat"}
STRUCTURAL_DISH_WORDS = {"pie", "bake", "wrap", "skillet", "casserole", "omelette", "omelet"}


@dataclass(frozen=True)
class FeasibilityResult:
    valid: bool
    reasons: list[str]
    roles: dict[str, list[str]]
    repaired_recipe: RecipeCandidate


def validate_and_repair_recipe(recipe: RecipeCandidate) -> FeasibilityResult:
    """Block physically unrealistic recipe drafts and rewrite to a safer dish form."""
    roles = {ingredient: classify_ingredient_roles(ingredient) for ingredient in recipe.ingredients_used}
    reasons = _invalid_reasons(recipe, roles)
    if not reasons:
        return FeasibilityResult(valid=True, reasons=[], roles=roles, repaired_recipe=recipe)

    repaired = _repair_recipe(recipe, roles, reasons)
    return FeasibilityResult(valid=False, reasons=reasons, roles=roles, repaired_recipe=repaired)


def classify_ingredient_roles(ingredient: str) -> list[str]:
    lowered = ingredient.lower()
    roles: list[str] = []
    if any(term in lowered for term in WET_SOFT_TERMS):
        roles.append("wet_soft")
    if any(term in lowered for term in BINDER_TERMS):
        roles.append("binder")
    if any(term in lowered for term in BASE_TERMS):
        roles.append("base")
    if any(term in lowered for term in PROTEIN_TERMS):
        roles.append("protein")
    if any(term in lowered for term in ["spinach", "tomato", "pepper", "onion", "carrot", "broccoli"]):
        roles.append("vegetable")
    if not roles:
        roles.append("other")
    return roles


def _invalid_reasons(recipe: RecipeCandidate, roles: dict[str, list[str]]) -> list[str]:
    title = recipe.title.lower()
    steps_text = " ".join(recipe.steps).lower()
    flat_roles = {role for item_roles in roles.values() for role in item_roles}
    reasons: list[str] = []

    if any(word in title for word in STRUCTURAL_DISH_WORDS):
        if "wrap" in title and "base" not in flat_roles:
            reasons.append("Dish title says wrap, but there is no tortilla, lavash, bread, or other base.")
        if any(word in title for word in ["pie", "bake", "casserole", "omelette", "omelet", "skillet"]):
            if "binder" not in flat_roles and "base" not in flat_roles:
                reasons.append("Dish type needs a binder or base, but none is available.")

    wet_soft_ingredients = [name for name, item_roles in roles.items() if "wet_soft" in item_roles]
    if wet_soft_ingredients and any(word in steps_text for word in ["cut", "slice", "chop"]):
        for ingredient in wet_soft_ingredients:
            if ingredient.lower() in steps_text:
                reasons.append(f"{ingredient} is soft/wet and should not be described as cuttable pieces.")

    if wet_soft_ingredients and any(word in title for word in ["crispy", "skillet", "seared"]):
        if "binder" not in flat_roles and "base" not in flat_roles:
            reasons.append("Mostly wet/soft ingredients will not become a crisp skillet dish without a binder or base.")

    if "yogurt" in steps_text and any(word in steps_text for word in ["high heat", "boil", "sear"]):
        reasons.append("Yogurt can curdle or split under high heat.")

    return reasons


def _repair_recipe(recipe: RecipeCandidate, roles: dict[str, list[str]], reasons: list[str]) -> RecipeCandidate:
    flat_roles = {role for item_roles in roles.values() for role in item_roles}
    wet_soft = [name for name, item_roles in roles.items() if "wet_soft" in item_roles]
    proteins = [name for name, item_roles in roles.items() if "protein" in item_roles or "binder" in item_roles]
    vegetables = [name for name, item_roles in roles.items() if "vegetable" in item_roles]

    if "binder" in flat_roles:
        title = _clean_title(recipe.title, "Skillet")
        steps = _egg_or_binder_steps(recipe)
    elif "base" in flat_roles:
        title = _clean_title(recipe.title, "Bowl")
        steps = _base_bowl_steps(recipe)
    elif wet_soft:
        title = _clean_title(recipe.title, "Protein Bowl")
        steps = _cold_or_gentle_bowl_steps(recipe, wet_soft, proteins, vegetables)
    else:
        title = _clean_title(recipe.title, "Simple Plate")
        steps = _simple_plate_steps(recipe)

    note = recipe.food_waste_note
    if reasons:
        note = note + " Feasibility check adjusted the dish form: " + " ".join(reasons)

    return recipe.model_copy(update={"title": title, "steps": steps, "food_waste_note": note})


def _clean_title(title: str, replacement: str) -> str:
    words = title.split()
    cleaned = [
        word
        for word in words
        if word.lower().strip("-:") not in STRUCTURAL_DISH_WORDS and word.lower() not in {"crispy"}
    ]
    base = " ".join(cleaned).strip() or "Fridge"
    if replacement.lower() not in base.lower():
        base = f"{base} {replacement}"
    return base


def _egg_or_binder_steps(recipe: RecipeCandidate) -> list[str]:
    return [
        f"Measure ingredients for {recipe.portions} portion(s): {_amount_text(recipe)}.",
        "Cut only firm vegetables or meats into 1 to 2 cm pieces; do not cut soft dairy or sauces.",
        "Heat a wide pan over medium heat for 2 minutes, then add a small amount of oil if available.",
        "Cook firm proteins or vegetables first for 3 to 6 minutes, stirring every minute, until hot and lightly softened.",
        "Add beaten eggs or other binder, lower to medium-low, and cook 2 to 4 minutes until just set; keep wet dairy off high heat and add it at the end if used.",
    ]


def _base_bowl_steps(recipe: RecipeCandidate) -> list[str]:
    return [
        f"Measure ingredients for {recipe.portions} portion(s): {_amount_text(recipe)}.",
        "Warm the base gently according to its type; use medium heat for 3 to 6 minutes for cooked grains or bread-like bases.",
        "Slice only firm proteins or vegetables; spoon soft dairy or sauces on top instead of cutting them.",
        "Assemble the warmed base with proteins, vegetables, and soft toppings.",
        "Taste and season with salt, pepper, acid, or herbs if available.",
    ]


def _cold_or_gentle_bowl_steps(
    recipe: RecipeCandidate,
    wet_soft: list[str],
    proteins: list[str],
    vegetables: list[str],
) -> list[str]:
    protein_text = ", ".join(proteins) if proteins else "available proteins"
    vegetable_text = ", ".join(vegetables) if vegetables else "any firm vegetables"
    soft_text = ", ".join(wet_soft)
    return [
        f"Measure ingredients for {recipe.portions} portion(s): {_amount_text(recipe)}.",
        f"Keep {soft_text} cold or gently warmed; do not sear or boil it because it can split or become watery.",
        f"Slice only firm items such as {protein_text} or {vegetable_text}; spoon soft dairy as a sauce or base.",
        "If using deli meat or cooked protein, warm it in a pan over medium-low heat for 1 to 2 minutes per side, or leave it cold for a bowl.",
        "Assemble as a high-protein bowl or spread plate, then season and serve immediately.",
    ]


def _simple_plate_steps(recipe: RecipeCandidate) -> list[str]:
    return [
        f"Measure ingredients for {recipe.portions} portion(s): {_amount_text(recipe)}.",
        "Separate firm ingredients from soft or wet ingredients.",
        "Warm firm cooked ingredients over medium heat for 3 to 5 minutes, stirring once or twice.",
        "Add soft ingredients after cooking as toppings or sauce.",
        "Taste and season before serving.",
    ]


def _amount_text(recipe: RecipeCandidate) -> str:
    return ", ".join(f"{amount.name}: {amount.total_amount}" for amount in recipe.ingredient_amounts)
