from __future__ import annotations

from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    quantity: str | None = None
    confidence: float = Field(ge=0, le=1)
    use_soon: bool = False
    possible_variants: list[str] = Field(default_factory=list)
    uncertainty_note: str | None = None


class IngredientExtractionResponse(BaseModel):
    ingredients: list[Ingredient]
    uncertain_items: list[str] = Field(default_factory=list)


class VerifiedIngredients(BaseModel):
    ingredients: list[Ingredient]
    clarification_questions: list[str] = Field(default_factory=list)
