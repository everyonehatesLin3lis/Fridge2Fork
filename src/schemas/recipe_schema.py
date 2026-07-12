from __future__ import annotations

from pydantic import BaseModel, Field


class NutritionEstimate(BaseModel):
    calories: int = Field(ge=0)
    protein_g: int = Field(ge=0)
    carbs_g: int = Field(ge=0)
    fat_g: int = Field(ge=0)
    calories_total: int | None = Field(default=None, ge=0)
    protein_total_g: int | None = Field(default=None, ge=0)
    estimated_daily_calorie_need: int | None = Field(default=None, ge=0)
    goal_note: str = "Based on the selected goal only; height and weight are optional rough context."
    note: str = "Approximate estimate only, not medical advice."


class IngredientAmount(BaseModel):
    name: str
    amount_per_portion: str
    total_amount: str
    notes: str | None = None


class RecipeCandidate(BaseModel):
    title: str = Field(min_length=1)
    description: str = ""
    time_minutes: int = Field(gt=0)
    prep_time_minutes: int = Field(default=10, gt=0)
    cook_time_minutes: int = Field(default=10, gt=0)
    portions: int = Field(default=1, gt=0)
    ingredients_used: list[str]
    ingredient_amounts: list[IngredientAmount] = Field(default_factory=list)
    missing_ingredients: list[str] = Field(default_factory=list)
    steps: list[str] = Field(min_length=1)


class RankedRecipe(BaseModel):
    candidate: RecipeCandidate
    nutrition: NutritionEstimate
    goal_fit: str
    rank_score: float


class SafeRecipe(BaseModel):
    ranked_recipe: RankedRecipe
    safety_warnings: list[str] = Field(default_factory=list)


class FinalRecipe(BaseModel):
    title: str
    description: str = ""
    time_minutes: int
    prep_time_minutes: int = 10
    cook_time_minutes: int = 10
    portions: int = 1
    ingredients_used: list[str]
    ingredient_amounts: list[IngredientAmount] = Field(default_factory=list)
    missing_ingredients: list[str]
    steps: list[str]
    nutrition: NutritionEstimate
    goal_fit: str
    safety_warnings: list[str] = Field(default_factory=list)
