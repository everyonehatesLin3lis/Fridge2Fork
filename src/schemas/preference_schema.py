from __future__ import annotations

from pydantic import BaseModel, Field


class UserPreferences(BaseModel):
    goal: str = Field(pattern="^(quick|healthy|high_protein|budget|comfort_food)$")
    allergies: list[str] = Field(default_factory=list)
    diet_style: str = "normal"
    max_cooking_time_minutes: int = Field(gt=0, le=360)
    meals_needed: int = Field(gt=0, le=14)
    meal_type: str = Field(default="dinner", pattern="^(breakfast|lunch|dinner|snack|meal_prep)$")
    constraint_resolution: str = Field(default="ask_first")
    gender: str = Field(default="none", pattern="^(male|female|none)$")
    height_cm: int | None = Field(default=None, gt=0, le=260)
    weight_kg: int | None = Field(default=None, gt=0, le=300)
    available_tools: list[str] = Field(default_factory=list)
