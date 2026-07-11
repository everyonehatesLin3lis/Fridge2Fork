from __future__ import annotations

from src.agents.vision_agent import run, verify_detected
from src.schemas.ingredient_schema import Ingredient, IngredientExtractionResponse


def test_low_confidence_ingredients_require_confirmation() -> None:
    detected = IngredientExtractionResponse(
        ingredients=[
            Ingredient(name="milk", category="dairy", confidence=0.49),
            Ingredient(name="eggs", category="protein", confidence=0.91),
        ],
        uncertain_items=[],
    )

    verified = verify_detected(detected)

    assert [ingredient.name for ingredient in verified.ingredients] == ["eggs"]
    assert "milk" in verified.clarification_questions[0]


def test_mock_image_does_not_return_fake_detected_food() -> None:
    result = run(image=b"fake image bytes")

    assert not result.detected_ingredients.ingredients
    assert "Mock mode cannot inspect" in result.detected_ingredients.uncertain_items[0]


def test_confirmed_ingredients_are_used_when_mock_image_cannot_be_inspected() -> None:
    result = run(image=b"fake image bytes", confirmed_ingredients=["rice"])

    names = {ingredient.name for ingredient in result.verified_ingredients.ingredients}

    assert "rice" in names


def test_multiple_images_are_limited_and_merged_in_mock_mode() -> None:
    result = run(image=[b"one", b"two", b"three", b"four", b"five", b"six"])

    assert len(result.image_results) == 5
    assert not result.detected_ingredients.ingredients
