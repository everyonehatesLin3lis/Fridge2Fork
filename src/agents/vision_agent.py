from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from src.config import get_settings
from src.schemas.ingredient_schema import Ingredient, IngredientExtractionResponse, VerifiedIngredients
from src.services.gemma_client import GemmaClient
from src.services.json_parser import parse_json_response
from src.services.telemetry import Stopwatch, log_event


class VisionAgentResult(BaseModel):
    detected_ingredients: IngredientExtractionResponse
    verified_ingredients: VerifiedIngredients
    low_confidence_items: list[dict[str, Any]]
    image_results: list[IngredientExtractionResponse] = []


def run(image: Any, confirmed_ingredients: list[str] | None = None) -> VisionAgentResult:
    """Detect, normalize, and verify fridge ingredients in one agent."""
    image_results = [_detect(single_image) for single_image in _as_image_list(image)]
    detected = _merge_detections(image_results)
    verified = _verify(detected)
    low_confidence_items = [
        ingredient.model_dump()
        for ingredient in detected.ingredients
        if ingredient.confidence < 0.5
    ]

    if confirmed_ingredients:
        confirmed_names = {name.strip().lower() for name in confirmed_ingredients if name.strip()}
        merged = [
            ingredient
            for ingredient in verified.ingredients
            if ingredient.name.strip().lower() not in confirmed_names
        ]
        merged.extend(_confirmed_ingredient(name) for name in confirmed_names)
        verified = VerifiedIngredients(
            ingredients=merged,
            clarification_questions=[
                question
                for question in verified.clarification_questions
                if not any(name in question.lower() for name in confirmed_names)
            ],
        )

    return VisionAgentResult(
        detected_ingredients=detected,
        verified_ingredients=verified,
        low_confidence_items=low_confidence_items,
        image_results=image_results,
    )


def verify_detected(detected: IngredientExtractionResponse) -> VerifiedIngredients:
    """Public helper for tests and future UI confirmation flows."""
    return _verify(detected)


def ingredient_from_confirmed_name(name: str) -> Ingredient:
    """Build a verified ingredient from user-typed confirmation text."""
    return _confirmed_ingredient(name)


def _detect(image: Any) -> IngredientExtractionResponse:
    if image is None:
        return IngredientExtractionResponse(ingredients=[], uncertain_items=[])

    settings = get_settings()
    if settings.app_mode == "mock":
        return IngredientExtractionResponse(
            ingredients=[],
            uncertain_items=[
                "Mock mode cannot inspect uploaded images. Use APP_MODE=local with Ollama, or type confirmed ingredients."
            ],
        )

    prompt = """
You are the Vision Agent for FridgeAgent.
Detect only visible food items in this fridge or food image.
Return only JSON with this exact shape:
{
  "ingredients": [
    {
      "name": "ingredient name",
      "category": "vegetable|fruit|protein|dairy|grain|sauce|other",
      "quantity": "visible rough quantity or null",
      "confidence": 0.0,
      "use_soon": false,
      "possible_variants": ["possible specific type if ambiguous"],
      "uncertainty_note": "why this matters, or null"
    }
  ],
  "uncertain_items": ["unclear item description"]
}
Do not invent hidden ingredients. If unsure, use lower confidence and add the item to uncertain_items.
Separate visible-object confidence from ingredient certainty by using lower confidence for unclear packages.
"""
    raw_response = ""
    error: Exception | None = None
    result: IngredientExtractionResponse | None = None
    with Stopwatch() as watch:
        try:
            raw_response = GemmaClient().generate_from_image(image, prompt)
            result = parse_json_response(raw_response, IngredientExtractionResponse)
        except (RuntimeError, ValueError) as exc:
            error = exc

    _log_detection_telemetry(settings, watch.elapsed_ms, raw_response, result, error)
    if result is not None:
        return result
    return IngredientExtractionResponse(
        ingredients=[],
        uncertain_items=[
            "The vision model could not parse the image. Confirm ingredients manually or retry with a clearer photo."
        ],
    )


def _log_detection_telemetry(
    settings: Any,
    latency_ms: float,
    raw_response: str,
    result: IngredientExtractionResponse | None,
    error: Exception | None,
) -> None:
    """Record one vision-detection data point so model quality can be tracked over time."""
    confidences = [ingredient.confidence for ingredient in result.ingredients] if result else []
    log_event(
        "vision_detection",
        {
            "app_mode": settings.app_mode,
            "model": settings.gemma_model_name if settings.app_mode == "local" else getattr(settings, "google_model_name", ""),
            "latency_ms": latency_ms,
            "parse_ok": result is not None,
            "error_type": type(error).__name__ if error else None,
            "error_message": str(error)[:200] if error else None,
            "raw_response_chars": len(raw_response),
            "ingredient_count": len(confidences),
            "uncertain_count": len(result.uncertain_items) if result else 0,
            "confidence_min": round(min(confidences), 3) if confidences else None,
            "confidence_mean": round(sum(confidences) / len(confidences), 3) if confidences else None,
            "confidence_max": round(max(confidences), 3) if confidences else None,
            "low_confidence_count": sum(1 for value in confidences if value < 0.5),
        },
    )


def _as_image_list(image: Any) -> list[Any]:
    if image is None:
        return []
    if isinstance(image, list):
        return image[:5]
    if isinstance(image, tuple):
        return list(image[:5])
    return [image]


def _merge_detections(results: list[IngredientExtractionResponse]) -> IngredientExtractionResponse:
    if not results:
        return IngredientExtractionResponse(ingredients=[], uncertain_items=[])

    by_name: dict[str, Ingredient] = {}
    uncertain_items: list[str] = []
    seen_uncertain: set[str] = set()

    for result in results:
        for ingredient in result.ingredients:
            key = ingredient.name.strip().lower()
            current = by_name.get(key)
            if current is None or ingredient.confidence > current.confidence:
                by_name[key] = ingredient.model_copy(update={"name": key})
        for item in result.uncertain_items:
            cleaned = item.strip()
            key = cleaned.lower()
            if cleaned and key not in seen_uncertain:
                seen_uncertain.add(key)
                uncertain_items.append(cleaned)

    return IngredientExtractionResponse(
        ingredients=list(by_name.values()),
        uncertain_items=uncertain_items,
    )


def _verify(detected: IngredientExtractionResponse) -> VerifiedIngredients:
    seen: set[str] = set()
    cleaned = []
    questions = [
        item
        if item.lower().startswith(("mock mode", "the vision model"))
        else f"I detected {item}. What is it?"
        for item in detected.uncertain_items
    ]

    for ingredient in detected.ingredients:
        normalized_name = ingredient.name.strip().lower()
        if normalized_name in seen:
            continue
        seen.add(normalized_name)

        if ingredient.confidence < 0.5:
            questions.append(
                f"I am not confident about '{ingredient.name}' "
                f"(confidence {ingredient.confidence:.2f}). Please confirm what this item is."
            )
            continue

        cleaned.append(ingredient.model_copy(update={"name": normalized_name}))

    return VerifiedIngredients(ingredients=cleaned, clarification_questions=questions)


def _mock_detection() -> IngredientExtractionResponse:
    return IngredientExtractionResponse(
        ingredients=[
            Ingredient(name="eggs", category="protein", quantity="6", confidence=0.92, use_soon=False),
            Ingredient(name="spinach", category="vegetable", quantity="1 bag", confidence=0.78, use_soon=True),
            Ingredient(
                name="Greek yogurt",
                category="dairy",
                quantity="1 tub",
                confidence=0.68,
                use_soon=True,
                possible_variants=["dairy Greek yogurt", "coconut yogurt"],
                uncertainty_note="The tub style is visible, but the exact base may affect dairy allergies.",
            ),
            Ingredient(name="cheddar cheese", category="dairy", quantity="small block", confidence=0.74, use_soon=False),
            Ingredient(name="tomatoes", category="vegetable", quantity="3", confidence=0.84, use_soon=True),
        ],
        uncertain_items=["white container on top shelf"],
    )


def _confirmed_ingredient(name: str) -> Ingredient:
    return Ingredient(
        name=name.strip().lower(),
        category=_category_for_confirmed(name),
        quantity=None,
        confidence=1.0,
        use_soon=False,
    )


def _category_for_confirmed(name: str) -> str:
    lowered = name.lower()
    if any(word in lowered for word in ["chicken", "beef", "pork", "turkey", "egg", "tofu", "fish"]):
        return "protein"
    if any(word in lowered for word in ["milk", "yogurt", "cheese", "butter", "cream"]):
        return "dairy"
    if any(word in lowered for word in ["rice", "pasta", "bread", "oat", "flour"]):
        return "grain"
    if any(word in lowered for word in ["apple", "banana", "berry", "orange", "lemon"]):
        return "fruit"
    if any(word in lowered for word in ["spinach", "tomato", "pepper", "onion", "carrot", "broccoli", "potato"]):
        return "vegetable"
    if any(word in lowered for word in ["sauce", "ketchup", "mustard", "mayo", "dressing"]):
        return "sauce"
    return "other"
