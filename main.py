from __future__ import annotations

import os
import re
from datetime import datetime

import streamlit as st

from src.orchestrator import run_fridge_agent_workflow
from src.services.gemma_client import GemmaClient
from src.services.hermes_agent_audit import run_hermes_agent_audit


os.environ.setdefault("APP_MODE", "local")
os.environ.setdefault("GEMMA_MODEL_NAME", "gemma4:e4b")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
monitor_slot = None


if "monitor_events" not in st.session_state:
    st.session_state.monitor_events = []
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "latest_result_json" not in st.session_state:
    st.session_state.latest_result_json = None


def add_monitor_event(agent_name: str, message: str, details: dict | None = None) -> None:
    st.session_state.monitor_events.append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "agent": agent_name,
            "message": message,
            "details": details or {},
        }
    )
    if monitor_slot is not None:
        render_monitor(monitor_slot)


def render_monitor(container=st) -> None:
    with container.container():
        st.subheader("Live agent monitor")
        st.caption(
            "This shows visible agent trace: inputs, outputs, uncertainty, assumptions, and summaries. "
            "It does not expose hidden chain-of-thought."
        )
        if not st.session_state.monitor_events:
            st.caption("Generate recipes to watch the multi-agent workflow here.")
            return

        for index, event in enumerate(reversed(st.session_state.monitor_events[-16:]), start=1):
            st.markdown(f"**{event['time']} - {event['agent']}**")
            st.caption(event["message"])
            if event["details"]:
                with st.expander(f"Inspect {event['agent']} trace #{index}", expanded=False):
                    if event["details"].get("reason_summary"):
                        st.info(event["details"]["reason_summary"])
                    st.json(event["details"])


def render_recipe_cards(result: object) -> None:
    st.subheader("Recipe cards")
    if not result.final_recipes:
        st.error(
            "No safe recipe cards were produced with the current constraints. Try confirming ambiguous ingredients, "
            "removing conflicting items, reducing allergies only if accurate, increasing time, or choosing best effort."
        )
        return

    for recipe in result.final_recipes:
        with st.container(border=True):
            st.markdown(f"### {recipe.title}")
            if recipe.passion_line:
                st.markdown(f"*{recipe.passion_line}*")
            st.write(
                f"**Portions:** {recipe.portions} | "
                f"**Prep:** {recipe.prep_time_minutes} min | "
                f"**Cook:** {recipe.cook_time_minutes} min | "
                f"**Total:** {recipe.time_minutes} min"
            )
            st.write(f"**Goal fit:** {recipe.goal_fit}")
            st.markdown("**Ingredient amounts**")
            if recipe.ingredient_amounts:
                st.table(
                    [
                        {
                            "Ingredient": amount.name,
                            "Per portion": amount.amount_per_portion,
                            f"Total for {recipe.portions}": amount.total_amount,
                            "Notes": amount.notes or "",
                        }
                        for amount in recipe.ingredient_amounts
                    ]
                )
            else:
                st.write("**Ingredients used:** " + ", ".join(recipe.ingredients_used))
            if recipe.missing_ingredients:
                st.write("**Missing ingredients:** " + ", ".join(recipe.missing_ingredients))
            st.markdown("**Steps**")
            for index, step in enumerate(recipe.steps, start=1):
                st.write(f"{index}. {step}")
            st.write(
                f"**Approx nutrition per portion:** {recipe.nutrition.calories} kcal, "
                f"{recipe.nutrition.protein_g}g protein, {recipe.nutrition.carbs_g}g carbs, "
                f"{recipe.nutrition.fat_g}g fat"
            )
            if recipe.nutrition.calories_total is not None:
                st.write(
                    f"**Approx recipe total:** {recipe.nutrition.calories_total} kcal, "
                    f"{recipe.nutrition.protein_total_g}g protein"
                )
            if recipe.nutrition.estimated_daily_calorie_need:
                st.write(
                    f"**Rough daily calorie context:** "
                    f"{recipe.nutrition.estimated_daily_calorie_need} kcal"
                )
            st.caption(recipe.nutrition.goal_note)
            st.caption(recipe.nutrition.note)
            st.info(recipe.food_waste_note)
            for warning in recipe.safety_warnings:
                st.warning(warning)


def build_chat_prompt(user_message: str) -> str:
    context = st.session_state.latest_result_json or "No recipes have been generated yet."
    return f"""
You are FridgeAgent's local cooking chat assistant.
Answer the user's question using the current recipe workflow context when relevant.
Be practical, brief, and allergy-conscious. Do not make medical claims.

Current workflow context:
{context}

User question:
{user_message}
"""


st.set_page_config(page_title="FridgeAgent Local", page_icon="F", layout="wide")

st.title("FridgeAgent Local")
st.caption("Local Streamlit deployment using Gemma 4 model `gemma4:e4b` through Ollama.")

with st.sidebar:
    st.subheader("Local model")
    st.code(f"APP_MODE={os.environ['APP_MODE']}\nGEMMA_MODEL_NAME={os.environ['GEMMA_MODEL_NAME']}\nOLLAMA_BASE_URL={os.environ['OLLAMA_BASE_URL']}")
    if st.button("Test Gemma 4 connection"):
        try:
            st.success(GemmaClient().health_check())
        except RuntimeError as exc:
            st.error(str(exc))
    if st.button("Clear monitor and chat"):
        st.session_state.monitor_events = []
        st.session_state.chat_messages = []
        st.session_state.latest_result_json = None
        st.rerun()

monitor_slot = st.empty()
render_monitor(monitor_slot)

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
    if os.getenv("APP_MODE", "local").lower() == "mock":
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
with st.form("local_preferences"):
    passion_note = st.text_input(
        "What are you passionate about cooking right now?",
        placeholder="e.g. my grandmother's garlic soup, or a match-day snack for when my team plays",
        help="Optional. This colors the recipe theme and adds a personal line to each recipe card.",
    )
    col_a, col_b = st.columns(2)
    with col_a:
        goal = st.selectbox("Cooking goal", ["quick", "healthy", "high_protein", "budget", "comfort_food"])
        meal_type = st.selectbox("Meal type", ["breakfast", "lunch", "dinner", "snack", "meal_prep"])
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
        constraint_resolution = st.radio(
            "If constraints conflict",
            ["ask_first", "reduce_portions", "increase_time", "make_best_effort"],
            format_func=lambda value: {
                "ask_first": "Ask me first",
                "reduce_portions": "Prefer fewer portions",
                "increase_time": "Prefer more cooking time",
                "make_best_effort": "Make best effort",
            }[value],
        )
        height_cm = st.number_input("Height cm (optional)", min_value=0, max_value=260, value=0)
        weight_kg = st.number_input("Weight kg (optional)", min_value=0, max_value=300, value=0)

    submitted = st.form_submit_button("Generate recipes")

if submitted:
    st.session_state.monitor_events = []
    if max_time <= 30 and int(meals_needed) >= 8 and constraint_resolution == "ask_first":
        st.warning(
            "This request may be unrealistic: 30 minutes for 8+ portions. Choose fewer portions, "
            "more time, or 'Make best effort' in the conflict option."
        )
        add_monitor_event(
            "Constraint Check",
            "Generation paused because the time and portion constraints conflict.",
            {
                "max_cooking_time_minutes": max_time,
                "portions_needed": int(meals_needed),
                "clarification_needed": "Do you want fewer portions, more time, or a best-effort meal-prep style plan?",
            },
        )
        render_monitor()
        st.stop()

    raw_preferences = {
        "goal": goal,
        "allergies": [item.strip() for item in allergies.split(",") if item.strip()],
        "diet_style": diet_style,
        "max_cooking_time_minutes": max_time,
        "meals_needed": int(meals_needed),
        "meal_type": meal_type,
        "constraint_resolution": constraint_resolution,
        "gender": gender,
        "height_cm": height_cm or None,
        "weight_kg": weight_kg or None,
        "available_tools": tools,
        "passion_note": passion_note.strip() or None,
    }
    confirmed_ingredients = [
        item.strip()
        for item in re.split(r"[,;\r\n]+", edited_ingredients)
        if item.strip()
    ]
    if confirmed_ingredients:
        raw_preferences["confirmed_ingredients"] = confirmed_ingredients

    result = run_fridge_agent_workflow(uploaded_image, raw_preferences, monitor=add_monitor_event)
    st.session_state.latest_result_json = result.model_dump_json(indent=2)
    render_recipe_cards(result)

    with st.expander("Ask local Gemma 4 to critique the plan"):
        prompt = (
            "You are helping test FridgeAgent. Briefly critique these recipe cards for practicality, "
            "allergy safety, and food-waste usefulness. Do not make medical claims.\n\n"
            f"{result.model_dump_json(indent=2)}"
        )
        if st.button("Run local Gemma 4 critique"):
            try:
                st.write(GemmaClient().generate_text(prompt))
            except RuntimeError as exc:
                st.error(str(exc))

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

st.subheader("Chat with FridgeAgent")
for message in st.session_state.chat_messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

chat_message = st.chat_input("Ask about the current recipes, ingredients, substitutions, or next changes")
if chat_message:
    st.session_state.chat_messages.append({"role": "user", "content": chat_message})
    with st.chat_message("user"):
        st.markdown(chat_message)

    with st.chat_message("assistant"):
        try:
            answer = GemmaClient().generate_text(build_chat_prompt(chat_message))
        except RuntimeError as exc:
            answer = str(exc)
        st.markdown(answer)

    st.session_state.chat_messages.append({"role": "assistant", "content": answer})
