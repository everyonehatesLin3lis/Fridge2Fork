"""FridgeAgent experience server.

Serves the redesigned single-page web experience (web/index.html) and a small
JSON API on top of the same four-agent workflow the Streamlit app uses.

Run:  .venv\\Scripts\\python.exe -m uvicorn server:app --port 8600
"""

from __future__ import annotations

import base64
import json
import os
import re

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("APP_MODE", "local")
os.environ.setdefault("GEMMA_MODEL_NAME", "gemma4:e4b")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
os.environ.setdefault("VISION_MODEL_NAME", "llava:7b")

from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Route

from src.orchestrator import run_fridge_agent_workflow
from src.services.gemma_client import GemmaClient

WEB_DIR = Path(__file__).parent / "web"

ADD_INTENT = re.compile(
    r"\b(buy|buying|bought|add|adding|added|getting|got|grab|grabbing|pick(ing)? up|purchase[ds]?)\b",
    re.IGNORECASE,
)

DEFAULT_PREFERENCES = {
    "goal": "quick",
    "allergies": [],
    "diet_style": "normal",
    "max_cooking_time_minutes": 30,
    "meals_needed": 2,
    "meal_type": "dinner",
    "constraint_resolution": "make_best_effort",
    "gender": "none",
    "height_cm": None,
    "weight_kg": None,
    "available_tools": ["pan", "pot", "oven"],
}


async def index(request):
    return FileResponse(WEB_DIR / "index.html")


def _decode_photos(items: list[str]) -> list[bytes]:
    photos = []
    for item in items:
        try:
            photos.append(base64.b64decode(item.split(",")[-1]))
        except (ValueError, TypeError):
            continue
    return [p for p in photos if p]


def _run_workflow(payload: dict) -> dict:
    preferences = {**DEFAULT_PREFERENCES, **(payload.get("preferences") or {})}
    ingredients = [
        str(item).strip().lower()
        for item in payload.get("ingredients") or []
        if str(item).strip()
    ]
    if ingredients:
        preferences["confirmed_ingredients"] = ingredients
    photos = _decode_photos(payload.get("photos") or [])

    result = run_fridge_agent_workflow(
        photos or None,
        preferences,
        avoid_recipe_titles=payload.get("avoid_titles") or None,
        featured_ingredients=payload.get("featured") or None,
    )
    return {
        "recipes": [recipe.model_dump() for recipe in result.final_recipes],
        "verified_ingredients": [
            {"name": i.name, "confidence": i.confidence}
            for i in result.verified_ingredients.ingredients
        ],
        "clarifications": result.verified_ingredients.clarification_questions,
        "context_json": result.model_dump_json(),
    }


async def api_recipes(request):
    payload = await request.json()
    try:
        data = await run_in_threadpool(_run_workflow, payload)
    except Exception as exc:  # surface a friendly error to the UI
        return JSONResponse({"error": str(exc)}, status_code=500)
    return JSONResponse(data)


def _extract_added_products(message: str) -> list[str]:
    if not ADD_INTENT.search(message):
        return []
    prompt = f"""
The user is chatting with a cooking app and may be mentioning food products they are adding or buying.
Extract ONLY the food product names from this message.
Return ONLY a JSON array of lowercase product name strings, nothing else.
If the user is not actually adding or buying any food product, return [].

Message: {message}
"""
    try:
        raw = GemmaClient().generate_text(prompt)
        start, end = raw.find("["), raw.rfind("]")
        if start < 0 or end <= start:
            return []
        items = json.loads(raw[start : end + 1])
        return [
            str(item).strip().lower()
            for item in items
            if isinstance(item, (str, int, float)) and 0 < len(str(item).strip()) <= 40
        ][:6]
    except (RuntimeError, ValueError):
        return []


def _chat_answer(message: str, context: str) -> str:
    prompt = f"""
You are FridgeAgent's friendly cooking chat assistant.
Answer the user's question using the current recipe workflow context when relevant.
Be practical, brief, warm, and allergy-conscious. Plain language, no jargon. No medical claims.

Current workflow context:
{context or "No recipes have been generated yet."}

User question:
{message}
"""
    return GemmaClient().generate_text(prompt)


async def api_chat(request):
    payload = await request.json()
    message = str(payload.get("message") or "").strip()
    if not message:
        return JSONResponse({"error": "empty message"}, status_code=400)

    added = await run_in_threadpool(_extract_added_products, message)
    if added:
        return JSONResponse({"type": "refresh", "added": added})
    try:
        answer = await run_in_threadpool(_chat_answer, message, str(payload.get("context") or ""))
    except RuntimeError as exc:
        answer = str(exc)
    return JSONResponse({"type": "answer", "answer": answer})


async def api_health(request):
    return JSONResponse({"ok": True, "mode": os.environ.get("APP_MODE", "local")})


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/recipes", api_recipes, methods=["POST"]),
        Route("/api/chat", api_chat, methods=["POST"]),
        Route("/api/health", api_health),
    ]
)
