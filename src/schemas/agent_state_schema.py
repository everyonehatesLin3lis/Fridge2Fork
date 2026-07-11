from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from src.schemas.ingredient_schema import IngredientExtractionResponse, VerifiedIngredients
from src.schemas.preference_schema import UserPreferences
from src.schemas.recipe_schema import FinalRecipe, RankedRecipe, RecipeCandidate, SafeRecipe


class AgentWorkflowState(BaseModel):
    detected_ingredients: IngredientExtractionResponse
    verified_ingredients: VerifiedIngredients
    preferences: UserPreferences
    recipe_candidates: list[RecipeCandidate]
    ranked_recipes: list[RankedRecipe]
    safe_recipes: list[SafeRecipe]
    final_recipes: list[FinalRecipe]
    steps_run: list[str] = Field(default_factory=list)
    hermes_trace: list[dict[str, Any]] = Field(default_factory=list)
