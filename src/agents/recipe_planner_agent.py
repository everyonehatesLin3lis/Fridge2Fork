from __future__ import annotations

import json
import re

from src.config import get_settings
from src.schemas.ingredient_schema import VerifiedIngredients
from src.schemas.preference_schema import UserPreferences
from src.schemas.recipe_schema import IngredientAmount, NutritionEstimate, RankedRecipe, RecipeCandidate
from src.services.gemma_client import GemmaClient
from src.services.json_parser import parse_json_list_response
from src.services.recipe_rag import RecipeRagStore, format_references_for_prompt
from src.utils.recipe_feasibility import validate_and_repair_recipe


def run(
    ingredients: VerifiedIngredients,
    preferences: UserPreferences,
    avoid_titles: list[str] | None = None,
    featured_ingredients: list[str] | None = None,
) -> tuple[list[RecipeCandidate], list[RankedRecipe]]:
    """Create practical recipes, calculate portions, and rank nutrition fit."""
    recipe_candidates = plan_recipes(ingredients, preferences, avoid_titles, featured_ingredients)
    ranked_recipes = rank_recipes(recipe_candidates, preferences)
    return recipe_candidates, ranked_recipes


def plan_recipes(
    ingredients: VerifiedIngredients,
    preferences: UserPreferences,
    avoid_titles: list[str] | None = None,
    featured_ingredients: list[str] | None = None,
) -> list[RecipeCandidate]:
    """Create practical recipe candidates from verified ingredients and preferences."""
    available = _normalize_ingredient_names([ingredient.name for ingredient in ingredients.ingredients])
    featured = _normalize_ingredient_names(featured_ingredients or [])
    if featured:
        # Featured products lead the list so they anchor fallback recipes too.
        available = list(dict.fromkeys([*featured, *available]))
    if not available:
        return []
    recipe_references = RecipeRagStore().search(
        ingredients=available,
        goal=preferences.goal,
        tools=preferences.available_tools,
        limit=3,
    )
    if get_settings().app_mode in {"local", "google"}:
        constraint_note = _constraint_note(preferences)
        reference_context = format_references_for_prompt(recipe_references)
        featured_note = (
            f"\nThe user just added these products and wants to cook with them: {json.dumps(featured)}. "
            "Every recipe MUST use them as a central ingredient, not a garnish.\n"
            if featured
            else ""
        )
        avoid_note = (
            f"\nThe user has already seen these recipes: {json.dumps(avoid_titles)}. "
            "Do NOT repeat them or offer close variations. Propose clearly different dishes: "
            "change the cooking technique, dish format, or cuisine.\n"
            if avoid_titles
            else ""
        )
        prompt = f"""
You are the Recipe Planner Agent for FridgeAgent.
Create 2 to 4 practical home recipes using these confirmed ingredients:
{json.dumps(available)}

User preferences:
{preferences.model_dump_json(indent=2)}

Constraint check:
{constraint_note}
{featured_note}{avoid_note}
Local recipe references retrieved from the Kaggle recipe dataset:
{reference_context}

Return only a JSON array. Each item must have exactly:
{{
  "title": "recipe title",
  "description": "one short appetizing sentence in plain everyday language that tells the user what this dish is and why they will like it",
  "time_minutes": 30,
  "prep_time_minutes": 10,
  "cook_time_minutes": 20,
  "portions": {preferences.meals_needed},
  "ingredients_used": ["ingredient from the confirmed list"],
  "ingredient_amounts": [
    {{
      "name": "ingredient name",
      "amount_per_portion": "100 g",
      "total_amount": "400 g",
      "notes": "rough amount or uncertainty"
    }}
  ],
  "missing_ingredients": ["small pantry item if needed"],
  "steps": ["short practical step"],
  "food_waste_note": "how this reduces waste"
}}

Rules:
- Use the confirmed ingredients above, not the default demo ingredients.
- Minimize missing ingredients.
- Respect allergies and diet style as much as possible.
- Respect meal_type. Breakfast should feel like breakfast, dinner like dinner, snack like snack, and meal_prep should scale better.
- Keep nutrition and health claims out of this step.
- Keep every recipe under {preferences.max_cooking_time_minutes} minutes.
- If servings and time conflict, do not pretend it is easy. Choose recipes that scale, use batch-friendly steps, and mention the compromise in food_waste_note.
- If an ingredient variant is ambiguous, avoid unsafe assumptions and keep the recipe compatible with the user's allergies where possible.
- Calculate ingredient amounts per portion and total amount for {preferences.meals_needed} portions.
- Base product quantities on the user's requested portion count. If the user asks for {preferences.meals_needed} portions, total_amount must equal amount_per_portion multiplied by {preferences.meals_needed}.
- Every ingredient in ingredients_used must have its own ingredient_amounts row with a measurement.
- Never combine multiple ingredients into one amount row. If the user has pasta, bacon, eggs, and parmesan, return four amount rows.
- If you do not know an exact amount, calculate a reasonable cooking estimate using g, ml, tbsp, tsp, cup, egg, clove, slice, or piece.
- Split total time into prep_time_minutes and cook_time_minutes.
- Use the retrieved local recipe references as grounding for cooking method, ingredient combinations, and timing, but adapt portions and constraints to this user.
- Steps must read like real cooking, not assembly notes.
- Write for a home cook who is not a chef: plain everyday words, no culinary jargon (say "cook until golden", not "saute until translucent" without explanation).
- Every step starts with an action verb and covers exactly one action, so the user can follow along step by step while cooking.
- The description must make someone instantly understand what the dish is; mention texture or flavor (creamy, crispy, fresh) when honest.
- Include cut size where it changes cooking time, such as thin slices, bite-size pieces, cubes, or whole pieces.
- Include heat level, pan/pot/oven/air fryer method, timing, stirring/flipping frequency, and doneness checks.
- For pan proteins, include minutes per side when relevant.
- For oven or air fryer recipes, include temperature and how piece size changes cooking time.
- Avoid vague steps like "cook until done" unless followed by a concrete doneness check.
"""
        try:
            return _validate_feasibility(
                _ensure_ingredient_amounts(
                    parse_json_list_response(GemmaClient().generate_text(prompt, creative=True), RecipeCandidate),
                    preferences.meals_needed,
                )
            )
        except (RuntimeError, ValueError):
            return _fallback_recipes(available, preferences, recipe_references)

    return _validate_feasibility(
        _ensure_ingredient_amounts(
            _fallback_recipes(available, preferences, recipe_references),
            preferences.meals_needed,
        )
    )


def rank_recipes(recipes: list[RecipeCandidate], preferences: UserPreferences) -> list[RankedRecipe]:
    """Rank recipes against the user's goal with approximate nutrition estimates."""
    ranked = []
    for recipe in recipes:
        base_calories, protein, carbs, fat = _estimate_from_ingredients(recipe)
        nutrition = NutritionEstimate(
            calories=base_calories,
            protein_g=protein,
            carbs_g=carbs,
            fat_g=fat,
            calories_total=base_calories * recipe.portions,
            protein_total_g=protein * recipe.portions,
            estimated_daily_calorie_need=_estimate_daily_calories(preferences),
            goal_note=_goal_note(preferences, protein, base_calories),
        )
        goal_fit = f"Good fit for {preferences.goal.replace('_', ' ')} using rough nutrition estimates."
        score = nutrition.protein_g if preferences.goal == "high_protein" else 80 - recipe.time_minutes
        ranked.append(RankedRecipe(candidate=recipe, nutrition=nutrition, goal_fit=goal_fit, rank_score=score))
    return sorted(ranked, key=lambda item: item.rank_score, reverse=True)


def _fallback_recipes(available: list[str], preferences: UserPreferences, recipe_references: list | None = None) -> list[RecipeCandidate]:
    available = _normalize_ingredient_names(available)
    if not available:
        return []
    primary = available[:4]
    title_bits = " ".join(item.title() for item in primary[:3])
    if recipe_references:
        title_bits = recipe_references[0].title[:48]
    prep_time = _prep_time(preferences)
    cook_time = _cook_time(preferences, primary)
    total_time = min(preferences.max_cooking_time_minutes, prep_time + cook_time)
    meal_label = preferences.meal_type.replace("_", " ").title()
    if preferences.meal_type == "snack":
        method = "Build small snack portions"
    elif preferences.meal_type == "meal_prep":
        method = "Batch-cook the base ingredients"
    else:
        method = "Cook the ingredients"
    primary_amounts = _estimate_amounts(primary, preferences.meals_needed)
    bowl_amounts = _estimate_amounts(primary[:3], preferences.meals_needed)
    return [
        RecipeCandidate(
            title=f"{MealPrefix.from_type(preferences.meal_type)} {title_bits} Skillet",
            description=f"Everything cooked together in one pan: {', '.join(primary[:3])} with simple seasoning, ready in about {total_time} minutes.",
            time_minutes=total_time,
            prep_time_minutes=prep_time,
            cook_time_minutes=max(5, total_time - prep_time),
            portions=preferences.meals_needed,
            ingredients_used=primary,
            ingredient_amounts=primary_amounts,
            missing_ingredients=["olive oil", "salt", "pepper"],
            steps=[
                f"Measure the ingredients: {', '.join(amount.total_amount + ' ' + amount.name for amount in primary_amounts)} for {preferences.meals_needed} portion(s).",
                f"Cut firm vegetables or proteins from {', '.join(primary)} into 1 to 2 cm bite-size pieces so they cook evenly; leave delicate greens larger because they wilt quickly.",
                "Heat a wide pan over medium heat for 2 minutes, then add 1 tablespoon oil per 4 portions.",
                _main_cooking_step(primary, preferences),
                _finish_step(primary, preferences, meal_label),
            ],
            food_waste_note=f"Uses {', '.join(primary[:2])} before they sit in the fridge too long.",
        ),
        RecipeCandidate(
            title=f"{meal_label} {primary[0].title()} Bowl",
            description=f"A quick warm bowl built around {primary[0]}, finished with a splash of something tangy so it tastes fresh, not like leftovers.",
            time_minutes=min(total_time, 30),
            prep_time_minutes=min(prep_time, 10),
            cook_time_minutes=max(5, min(total_time, 30) - min(prep_time, 10)),
            portions=preferences.meals_needed,
            ingredients_used=primary[:3],
            ingredient_amounts=bowl_amounts,
            missing_ingredients=["lemon juice or vinegar", "black pepper"],
            steps=[
                f"Measure the bowl base: {', '.join(amount.total_amount + ' ' + amount.name for amount in bowl_amounts)}.",
                f"Prep {primary[0]} first: slice thin if it is firm, chop bite-size if it is tender, or keep it whole only if it is already cooked.",
                _bowl_cooking_step(primary[:3], preferences),
                f"Divide into {preferences.meals_needed} {meal_label.lower()} portion(s), then finish each portion with a small splash of lemon juice or vinegar and black pepper.",
            ],
            food_waste_note="Turns small leftover portions into a fast meal instead of letting them expire.",
        ),
    ]


class MealPrefix:
    @staticmethod
    def from_type(meal_type: str) -> str:
        return {
            "breakfast": "Breakfast",
            "lunch": "Lunch",
            "dinner": "Dinner",
            "snack": "Snack",
            "meal_prep": "Meal Prep",
        }.get(meal_type, "Quick")


def _constraint_note(preferences: UserPreferences) -> str:
    if preferences.max_cooking_time_minutes <= 30 and preferences.meals_needed >= 8:
        return (
            "Potential conflict: many portions in a short time. Ask for clarification if allowed, "
            "or choose batch-friendly no-fuss recipes and clearly state the tradeoff."
        )
    if preferences.max_cooking_time_minutes <= 30:
        return "Short cooking window. Prefer minimal prep, one-pan, raw, or assembly-style recipes."
    if preferences.max_cooking_time_minutes >= 240:
        return "Long cooking window. Slow braises, roasting, batch cooking, chilling, and simmering are available when useful."
    return "No major time and serving conflict detected."


def _estimate_amounts(ingredients: list[str], portions: int) -> list[IngredientAmount]:
    return [
        IngredientAmount(
            name=ingredient,
            amount_per_portion=_amount_per_portion(ingredient),
            total_amount=_scaled_amount(ingredient, portions),
            notes=f"Calculated for {portions} portion(s): per-portion amount multiplied by requested portions.",
        )
        for ingredient in ingredients
    ]


def _ensure_ingredient_amounts(recipes: list[RecipeCandidate], portions: int) -> list[RecipeCandidate]:
    normalized = []
    for recipe in recipes:
        ingredients_used = _normalize_ingredient_names(recipe.ingredients_used)
        existing = {
            amount.name.strip().lower(): amount
            for amount in recipe.ingredient_amounts
        }
        completed_amounts = []
        for ingredient in ingredients_used:
            key = ingredient.strip().lower()
            completed_amounts.append(existing.get(key) or _estimate_amounts([ingredient], portions)[0])
        normalized.append(
            recipe.model_copy(
                update={
                    "portions": portions,
                    "ingredients_used": ingredients_used,
                    "ingredient_amounts": completed_amounts,
                }
            )
        )
    return normalized


def _validate_feasibility(recipes: list[RecipeCandidate]) -> list[RecipeCandidate]:
    return [validate_and_repair_recipe(recipe).repaired_recipe for recipe in recipes]


def _normalize_ingredient_names(ingredients: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for ingredient in ingredients:
        for item in re.split(r"[,;\r\n]+", str(ingredient)):
            cleaned = item.strip(" -\t").lower()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                normalized.append(cleaned)
    return normalized


def _amount_per_portion(ingredient: str) -> str:
    lowered = ingredient.lower()
    if "bacon" in lowered:
        return "30 g"
    if any(word in lowered for word in ["chicken", "beef", "pork", "turkey", "tofu", "fish"]):
        return "120 g"
    if any(word in lowered for word in ["rice", "pasta", "beans", "corn", "potato"]):
        return "75 g"
    if any(word in lowered for word in ["egg", "eggs"]):
        return "1 egg (about 50 g)"
    if any(word in lowered for word in ["milk", "yogurt"]):
        return "120 ml"
    if any(word in lowered for word in ["parmesan"]):
        return "15 g"
    if any(word in lowered for word in ["cheese"]):
        return "30 g"
    if any(word in lowered for word in ["spinach", "tomato", "vegetable"]):
        return "80 g"
    if any(word in lowered for word in ["onion", "pepper", "carrot", "broccoli", "mushroom", "zucchini"]):
        return "80 g"
    return "100 g"


def _scaled_amount(ingredient: str, portions: int) -> str:
    per_portion = _amount_per_portion(ingredient)
    if "egg" in per_portion and "50 g" in per_portion:
        return f"{portions} eggs (about {portions * 50} g)"
    if per_portion.endswith(" ml"):
        amount = int(per_portion.split()[0]) * portions
        return f"{amount} ml"
    if per_portion.endswith(" g"):
        amount = int(per_portion.split()[0]) * portions
        return f"{amount} g"
    return f"{per_portion} x {portions}"


def _prep_time(preferences: UserPreferences) -> int:
    if preferences.meals_needed >= 8:
        return 20
    if preferences.meals_needed >= 4:
        return 15
    return 10


def _cook_time(preferences: UserPreferences, ingredients: list[str]) -> int:
    lowered = " ".join(ingredients).lower()
    available = max(5, preferences.max_cooking_time_minutes - _prep_time(preferences))
    if preferences.max_cooking_time_minutes >= 240 and any(
        word in lowered for word in ["chicken", "beef", "pork", "beans", "potato"]
    ):
        return min(available, 180)
    if preferences.max_cooking_time_minutes >= 120:
        return min(available, 90)
    if preferences.meals_needed > 6:
        return min(available, 60)
    return min(available, 45)


def _main_cooking_step(ingredients: list[str], preferences: UserPreferences) -> str:
    lowered = " ".join(ingredients).lower()
    portions_note = "work in batches so the pan is not crowded" if preferences.meals_needed > 4 else "keep the pieces in one even layer"
    if "chicken" in lowered:
        return (
            f"Add chicken pieces first and {portions_note}; cook on medium-high heat for 4 to 5 minutes per side "
            "for 1 to 2 cm pieces, or 7 to 8 minutes per side for whole thicker pieces. Chicken is ready when no pink remains "
            "in the center and the juices run clear."
        )
    if "egg" in lowered:
        return (
            "Add vegetables first for 3 to 5 minutes, stirring every minute, then lower to medium-low and add beaten eggs; "
            "stir gently for 2 to 3 minutes until the eggs are set but still moist."
        )
    if any(item in lowered for item in ["rice", "pasta", "potato"]):
        return (
            "Add the firm starch or grains with 2 tablespoons water, cover for 5 minutes to heat through, then uncover and cook "
            "3 to 4 minutes more so edges pick up light browning."
        )
    return (
        f"{preferences.meal_type.replace('_', ' ').title()} cooking step: add the firmest pieces first and {portions_note}; "
        "cook on medium heat for 6 to 8 minutes, stirring every 1 to 2 minutes, until firm pieces are tender and greens are wilted."
    )


def _bowl_cooking_step(ingredients: list[str], preferences: UserPreferences) -> str:
    lowered = " ".join(ingredients).lower()
    if any(item in lowered for item in ["rice", "beans", "pasta"]):
        return (
            "Warm the cooked grain or beans in a covered pan with 2 tablespoons water for 4 to 6 minutes, stirring halfway; "
            "add tender vegetables at the end so they soften without collapsing."
        )
    if "egg" in lowered:
        return (
            "Cook eggs in a lightly oiled pan over medium-low heat for 2 to 4 minutes, stirring for soft curds or flipping once "
            "for a firmer omelet-style topping."
        )
    if preferences.meal_type == "snack":
        return "Keep crunchy items raw and only warm cooked leftovers for 2 to 3 minutes so the snack does not turn soggy."
    return "Warm cooked ingredients over medium heat for 4 to 6 minutes; keep raw crisp ingredients separate until serving."


def _finish_step(ingredients: list[str], preferences: UserPreferences, meal_label: str) -> str:
    lowered = " ".join(ingredients).lower()
    if preferences.meals_needed > 4:
        portion_note = "Spread portions in shallow containers so they cool quickly before refrigeration."
    else:
        portion_note = f"Serve immediately or divide into {preferences.meals_needed} {meal_label.lower()} portion(s)."
    if "spinach" in lowered:
        return f"Fold spinach or delicate greens in during the final 60 to 90 seconds only, then season with salt and pepper. {portion_note}"
    return f"Season with salt and pepper, taste once, and adjust with acid if available. {portion_note}"


def _estimate_daily_calories(preferences: UserPreferences) -> int | None:
    if not preferences.weight_kg:
        return None
    if preferences.height_cm and preferences.gender in {"male", "female"}:
        # Mifflin-St Jeor without age input, using a neutral adult demo age.
        age = 30
        sex_adjustment = 5 if preferences.gender == "male" else -161
        base = round((10 * preferences.weight_kg) + (6.25 * preferences.height_cm) - (5 * age) + sex_adjustment)
    else:
        base = preferences.weight_kg * 30
    if preferences.goal == "comfort_food":
        return base + 150
    return base


def _goal_note(preferences: UserPreferences, protein_g: int, calories: int) -> str:
    pieces = [f"Per portion estimate: {calories} kcal and {protein_g} g protein."]
    if preferences.weight_kg:
        protein_target = round(preferences.weight_kg * 1.6)
        pieces.append(
            f"For high-protein planning, a rough daily protein reference could be about {protein_target} g based on weight."
        )
    if preferences.height_cm and preferences.weight_kg:
        if preferences.gender in {"male", "female"}:
            pieces.append(
                f"Height, weight, and gender ({preferences.gender}) were used only as rough nutrition context, not as a medical target."
            )
        else:
            pieces.append("Height and weight were used only as rough context, not as a medical target.")
    pieces.append(f"Goal selected: {preferences.goal.replace('_', ' ')}.")
    return " ".join(pieces)


def _estimate_from_ingredients(recipe: RecipeCandidate) -> tuple[int, int, int, int]:
    calories = 90
    protein = 4
    carbs = 6
    fat = 5

    ingredient_names = recipe.ingredients_used
    if recipe.ingredient_amounts:
        ingredient_names = [amount.name for amount in recipe.ingredient_amounts]

    for name in ingredient_names:
        lowered = name.lower()
        if "chicken" in lowered:
            calories += 200
            protein += 34
            fat += 5
        elif "egg" in lowered:
            calories += 72
            protein += 6
            fat += 5
        elif "yogurt" in lowered:
            calories += 90
            protein += 10
            carbs += 6
        elif any(word in lowered for word in ["rice", "pasta", "potato", "corn"]):
            calories += 110
            carbs += 24
            protein += 2
        elif any(word in lowered for word in ["beans", "lentil"]):
            calories += 120
            carbs += 20
            protein += 8
        elif any(word in lowered for word in ["cheese", "cheddar"]):
            calories += 120
            protein += 7
            fat += 10
        elif any(word in lowered for word in ["spinach", "tomato", "onion", "pepper", "carrot", "broccoli"]):
            calories += 30
            carbs += 6
            protein += 1
        else:
            calories += 60
            carbs += 8
            protein += 2

    if recipe.missing_ingredients:
        calories += 40
        fat += 3

    return calories, protein, carbs, fat
