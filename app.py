from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any

import streamlit as st
from dotenv import load_dotenv

from src.orchestrator import run_fridge_agent_workflow
from src.services.gemma_client import GemmaClient
from src.services.hermes_agent_audit import run_hermes_agent_audit


# Load .env before applying defaults so APP_MODE from .env is respected.
load_dotenv()
os.environ.setdefault("APP_MODE", "mock")


if "monitor_events" not in st.session_state:
    st.session_state.monitor_events = []


def compact_details(value: Any, depth: int = 0) -> Any:
    """Shrink monitor payloads so debug rendering stays light.

    Full agent outputs stay available in the 'Agent outputs' expander; shipping
    full RAG reference dumps and model dumps for every event can freeze the
    browser tab.
    """
    if depth >= 4:
        return "..."
    if isinstance(value, dict):
        return {key: compact_details(item, depth + 1) for key, item in list(value.items())[:16]}
    if isinstance(value, list):
        compacted = [compact_details(item, depth + 1) for item in value[:4]]
        if len(value) > 4:
            compacted.append(f"... {len(value) - 4} more items")
        return compacted
    if isinstance(value, str) and len(value) > 240:
        return value[:240] + "..."
    return value


def add_monitor_event(agent_name: str, message: str, details: dict[str, Any] | None = None) -> None:
    st.session_state.monitor_events.append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "agent": agent_name,
            "message": message,
            "details": compact_details(details or {}),
        }
    )


def render_monitor() -> None:
    st.subheader("Live debug")
    if not st.session_state.monitor_events:
        st.caption("Generate recipes to see the agent handoffs, inputs, outputs, and summaries.")
        return
    for index, event in enumerate(st.session_state.monitor_events, start=1):
        st.markdown(f"**{index}. {event['time']} - {event['agent']}**")
        st.caption(event["message"])
        if event["details"]:
            with st.expander(f"Inspect {event['agent']} payload #{index}", expanded=False):
                if event["details"].get("reason_summary"):
                    st.info(event["details"]["reason_summary"])
                st.json(event["details"])


def recipe_metrics(result: Any) -> dict[str, Any]:
    recipes = result.final_recipes
    return {
        "hermes_stage_count": len(result.steps_run),
        "final_recipe_count": len(recipes),
        "avg_cooking_detail_score": _average([_cooking_detail_score(recipe.steps) for recipe in recipes]),
        "avg_portion_amount_coverage": _average(
            [len(recipe.ingredient_amounts) / max(len(recipe.ingredients_used), 1) for recipe in recipes]
        ),
        "recipes_with_total_nutrition": sum(
            1
            for recipe in recipes
            if recipe.nutrition.calories_total is not None and recipe.nutrition.protein_total_g is not None
        ),
    }


def render_recipe_cards(result: Any) -> None:
    st.subheader("Recipe cards")
    if not result.final_recipes:
        if not result.verified_ingredients.ingredients:
            st.error(
                "No recipes were generated because no ingredients could be verified. "
                "The vision model did not return usable detections from the uploaded photo(s)."
            )
            for question in result.verified_ingredients.clarification_questions:
                st.warning(question)
            st.info(
                "Type your ingredients into the 'Confirmed ingredients' box above and press "
                "Generate recipes again. Typed ingredients always work, even when photo detection fails."
            )
        else:
            st.error("No safe recipe cards were produced with the current constraints.")
        return

    for recipe in result.final_recipes:
        with st.container(border=True):
            st.markdown(f"### {recipe.title}")
            st.write(
                f"**Portions:** {recipe.portions} | "
                f"**Prep:** {recipe.prep_time_minutes} min | "
                f"**Cook:** {recipe.cook_time_minutes} min | "
                f"**Total:** {recipe.time_minutes} min | "
                f"**Calories/portion:** ≈ {recipe.nutrition.calories} kcal"
            )
            st.write(f"**Goal fit:** {recipe.goal_fit}")
            st.write("**Ingredients used:** " + ", ".join(recipe.ingredients_used))
            if recipe.ingredient_amounts:
                st.markdown("**Product amounts for requested portions**")
                st.table(
                    [
                        {
                            "Ingredient": amount.name,
                            "Per portion": amount.amount_per_portion,
                            f"Total for {recipe.portions}": amount.total_amount,
                            "Calculation note": amount.notes or "",
                        }
                        for amount in recipe.ingredient_amounts
                    ]
                )
            if recipe.missing_ingredients:
                st.write("**Missing ingredients:** " + ", ".join(recipe.missing_ingredients))
            st.markdown("**Cooking steps**")
            for index, step in enumerate(recipe.steps, start=1):
                st.write(f"{index}. {step}")
            st.write(
                f"**Approx nutrition per portion:** {recipe.nutrition.calories} kcal, "
                f"{recipe.nutrition.protein_g}g protein, {recipe.nutrition.carbs_g}g carbs, "
                f"{recipe.nutrition.fat_g}g fat"
            )
            if recipe.nutrition.calories_total is not None:
                st.write(
                    f"**Approx total for {recipe.portions} portions:** "
                    f"{recipe.nutrition.calories_total} kcal, "
                    f"{recipe.nutrition.protein_total_g}g protein"
                )
            st.caption(recipe.nutrition.goal_note)
            st.caption(recipe.nutrition.note)
            for warning in recipe.safety_warnings:
                st.warning(warning)


def _cooking_detail_score(steps: list[str]) -> float:
    text = " ".join(steps).lower()
    checks = [
        any(word in text for word in ["medium", "high heat", "low heat", "oven", "air fryer"]),
        "minute" in text,
        any(word in text for word in ["cm", "bite-size", "slice", "whole", "pieces"]),
        any(word in text for word in ["stir", "flip", "cover", "uncover"]),
        any(word in text for word in ["ready", "tender", "set", "no pink", "juices run clear", "wilted"]),
    ]
    return round(sum(checks) / len(checks), 2)


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 2)


st.set_page_config(page_title="FridgeAgent", page_icon="F", layout="wide")

st.title("FridgeAgent")
st.caption("Let four AI agents handle the meal-idea thinking so you can start cooking sooner.")

with st.sidebar:
    st.subheader("Local status")
    st.code(
        "APP_MODE="
        + os.getenv("APP_MODE", "mock")
        + "\nGEMMA_MODEL_NAME="
        + os.getenv("GEMMA_MODEL_NAME", "gemma4:e4b")
        + "\nOLLAMA_BASE_URL="
        + os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    )
    st.success("Streamlit app is running locally.")
    if os.path.exists("data/recipe_rag_index.jsonl"):
        st.success("Recipe RAG index is available.")
    else:
        st.warning("Recipe RAG index not built yet.")
    if st.button("Check model connection"):
        try:
            st.success(GemmaClient().health_check())
        except RuntimeError as exc:
            st.error(str(exc))

uploaded_image = st.file_uploader(
    "Upload up to 5 fridge or food photos",
    type=["jpg", "jpeg", "png", "webp"],
    accept_multiple_files=True,
)

if uploaded_image:
    if len(uploaded_image) > 5:
        st.error("Please upload at most 5 photos.")
        st.stop()
    st.image(uploaded_image, caption=[f"Uploaded food photo {index}" for index in range(1, len(uploaded_image) + 1)], width="stretch")
    if os.getenv("APP_MODE", "mock").lower() == "mock":
        st.warning(
            "APP_MODE=mock cannot inspect uploaded images. Switch to APP_MODE=local and run Ollama, "
            "or type confirmed ingredients below."
        )

st.subheader("Detected ingredient review")
edited_ingredients = st.text_area(
    "Confirmed ingredients",
    value="",
    placeholder="Leave blank to use photo detection, or type ingredients like rice, beans, corn",
    help="Separate ingredients with commas. Typed ingredients override photo detection.",
)

st.subheader("Preferences")
with st.form("preferences"):
    col_a, col_b = st.columns(2)
    with col_a:
        goal = st.selectbox("Cooking goal", ["quick", "healthy", "high_protein", "budget", "comfort_food"])
        diet_style = st.selectbox("Diet style", ["normal", "vegetarian", "vegan", "gluten_free", "dairy_free"])
        max_time = st.select_slider("Max cooking time", options=[30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330, 360], value=30)
        meals_needed = st.number_input("Portions needed", min_value=1, max_value=14, value=2)
    with col_b:
        allergies = st.text_input("Allergies", placeholder="peanuts, dairy, gluten")
        tools = st.multiselect(
            "Available tools",
            ["pan", "pot", "oven", "microwave", "air fryer", "blender"],
            default=["pan", "oven"],
        )
        gender = st.selectbox("Gender for nutrition estimate", ["none", "male", "female"])
        height_cm = st.number_input("Height cm (optional)", min_value=0, max_value=260, value=0)
        weight_kg = st.number_input("Weight kg (optional)", min_value=0, max_value=300, value=0)

    submitted = st.form_submit_button("Generate recipes")

if submitted:
    st.session_state.monitor_events = []
    raw_preferences = {
        "goal": goal,
        "allergies": [item.strip() for item in allergies.split(",") if item.strip()],
        "diet_style": diet_style,
        "max_cooking_time_minutes": max_time,
        "meals_needed": int(meals_needed),
        "gender": gender,
        "height_cm": height_cm or None,
        "weight_kg": weight_kg or None,
        "available_tools": tools,
    }
    confirmed_ingredients = [
        item.strip()
        for item in re.split(r"[,;\r\n]+", edited_ingredients)
        if item.strip()
    ]
    if confirmed_ingredients:
        raw_preferences["confirmed_ingredients"] = confirmed_ingredients

    with st.spinner("Running the four-agent workflow..."):
        result = run_fridge_agent_workflow(uploaded_image, raw_preferences, monitor=add_monitor_event)
    st.session_state.latest_result = result

result = st.session_state.get("latest_result")
if result is not None:
    metrics = recipe_metrics(result)
    st.subheader("Run metrics")
    metric_cols = st.columns(5)
    metric_cols[0].metric("Hermes stages", metrics["hermes_stage_count"])
    metric_cols[1].metric("Recipe cards", metrics["final_recipe_count"])
    metric_cols[2].metric("Cooking detail", metrics["avg_cooking_detail_score"])
    metric_cols[3].metric("Amount coverage", metrics["avg_portion_amount_coverage"])
    metric_cols[4].metric("Nutrition totals", metrics["recipes_with_total_nutrition"])
    st.caption("Cooking detail is a simple debug score checking for heat, timing, cut size, movement, and doneness cues.")

    render_monitor()

    render_recipe_cards(result)

    with st.expander("Run Hermes Agent audit"):
        st.caption(
            "Uses the real `hermes chat -Q -q` CLI when Hermes Agent is installed. "
            "If the CLI is missing, the app shows setup guidance and a deterministic fallback audit."
        )
        if st.button("Run Hermes Agent Audit"):
            with st.spinner("Asking Hermes Agent to audit the workflow..."):
                audit = run_hermes_agent_audit(result.model_dump())
            st.json(audit)

    with st.expander("Agent outputs"):
        st.json(result.model_dump())
