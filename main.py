from __future__ import annotations

import json
import os
import re
from datetime import datetime

import streamlit as st
from dotenv import load_dotenv

from src.orchestrator import run_fridge_agent_workflow
from src.services.gemma_client import GemmaClient
from src.services.hermes_agent_audit import run_hermes_agent_audit


# Load .env before applying defaults so APP_MODE from .env is respected.
load_dotenv()
os.environ.setdefault("APP_MODE", "local")
os.environ.setdefault("GEMMA_MODEL_NAME", "gemma4:e4b")
os.environ.setdefault("OLLAMA_BASE_URL", "http://localhost:11434")
# gemma4:e4b's Ollama vision path is unreliable; photos go to a dedicated vision model.
os.environ.setdefault("VISION_MODEL_NAME", "llava:7b")

SURPRISE_INGREDIENTS = ["eggs", "pasta", "rice", "onion", "tomatoes", "cheese"]

MEAL_OPTIONS = [
    ("breakfast", "🍳 Breakfast"),
    ("lunch", "🥪 Lunch"),
    ("dinner", "🍝 Dinner"),
    ("snack", "🍿 Snacks"),
    ("meal_prep", "🍱 Meal prep"),
]

GOAL_OPTIONS = [
    ("quick", "⚡ Quick & easy"),
    ("healthy", "🥗 Healthy"),
    ("high_protein", "💪 High protein"),
    ("budget", "💸 Budget"),
    ("comfort_food", "🛋️ Comfort food"),
]


def init_state() -> None:
    defaults = {
        "step": 1,
        "ingredient_mode": None,  # "photo" | "typed" | "surprise"
        "typed_ingredients": "",
        "uploaded_photos": None,
        "meal_type": None,
        "goal": None,
        "monitor_events": [],
        "chat_messages": [],
        "latest_result": None,
        "latest_result_json": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def go_to_step(step: int) -> None:
    st.session_state.step = step
    st.rerun()


def compact_details(value: object, depth: int = 0) -> object:
    """Shrink monitor payloads so live trace rendering stays light.

    Full agent outputs stay available in the 'Behind the scenes' expander; the
    live monitor only needs summaries. Shipping full RAG reference dumps and
    model dumps on every event can freeze the browser tab and kill the run.
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


def add_monitor_event(agent_name: str, message: str, details: dict | None = None) -> None:
    st.session_state.monitor_events.append(
        {
            "time": datetime.now().strftime("%H:%M:%S"),
            "agent": agent_name,
            "message": message,
            "details": compact_details(details or {}),
        }
    )


def wizard_header(step: int, total: int, title: str, subtitle: str = "") -> None:
    st.progress(step / total, text=f"Step {step} of {total}")
    st.title(title)
    if subtitle:
        st.caption(subtitle)


def back_button(step: int) -> None:
    if st.button("← Back", key=f"back_{step}"):
        go_to_step(step - 1)


# ---------------------------------------------------------------- Step 1

def render_step_ingredients() -> None:
    wizard_header(1, 4, "🍳 Sup! What are we cooking with today?",
                  "Pick whichever is easiest — you can always adjust later.")

    col_photo, col_type, col_surprise = st.columns(3)
    with col_photo:
        if st.button("📷 Snap my fridge", width="stretch",
                     type="primary" if st.session_state.ingredient_mode == "photo" else "secondary"):
            st.session_state.ingredient_mode = "photo"
            st.rerun()
        st.caption("Upload up to 5 photos of your fridge or food")
    with col_type:
        if st.button("⌨️ I'll type my products", width="stretch",
                     type="primary" if st.session_state.ingredient_mode == "typed" else "secondary"):
            st.session_state.ingredient_mode = "typed"
            st.rerun()
        st.caption("Just list what you have at home")
    with col_surprise:
        if st.button("🎲 Skip — surprise me", width="stretch",
                     type="primary" if st.session_state.ingredient_mode == "surprise" else "secondary"):
            st.session_state.ingredient_mode = "surprise"
            st.rerun()
        st.caption("We'll cook with everyday staples")

    st.divider()
    mode = st.session_state.ingredient_mode
    ready = False

    if mode == "photo":
        photos = st.file_uploader(
            "Show me what's in there",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True,
        )
        if photos:
            if len(photos) > 5:
                st.error("Five photos max, please!")
            else:
                # Copy the raw bytes now: Streamlit frees uploaded files once
                # the uploader widget leaves the screen on the next steps.
                st.session_state.uploaded_photos = [photo.getvalue() for photo in photos]
        if st.session_state.uploaded_photos:
            st.image(st.session_state.uploaded_photos, width=160)
            st.caption(f"{len(st.session_state.uploaded_photos)} photo(s) locked in ✅")
            ready = True
        if os.getenv("APP_MODE", "local").lower() == "mock":
            st.warning("Demo mode can't look at photos — type your products instead.")
    elif mode == "typed":
        st.session_state.typed_ingredients = st.text_area(
            "What have you got? Separate with commas",
            value=st.session_state.typed_ingredients,
            placeholder="e.g. chicken, rice, onion, tomatoes",
        )
        ready = bool(st.session_state.typed_ingredients.strip())
    elif mode == "surprise":
        st.info("We'll assume everyday staples: " + ", ".join(SURPRISE_INGREDIENTS)
                + ". Swap to typing your own products any time.")
        ready = True

    if ready and st.button("Next →", type="primary", width="stretch"):
        go_to_step(2)


# ---------------------------------------------------------------- Step 2

def render_step_meal() -> None:
    wizard_header(2, 4, "🍽️ What's the occasion?", "Are we cooking for...")
    columns = st.columns(len(MEAL_OPTIONS))
    for column, (value, label) in zip(columns, MEAL_OPTIONS):
        with column:
            if st.button(label, width="stretch",
                         type="primary" if st.session_state.meal_type == value else "secondary"):
                st.session_state.meal_type = value
                go_to_step(3)
    st.divider()
    back_button(2)


# ---------------------------------------------------------------- Step 3

def render_step_goal() -> None:
    wizard_header(3, 4, "✨ What's the vibe today?", "Pick what matters most right now.")
    columns = st.columns(len(GOAL_OPTIONS))
    for column, (value, label) in zip(columns, GOAL_OPTIONS):
        with column:
            if st.button(label, width="stretch",
                         type="primary" if st.session_state.goal == value else "secondary"):
                st.session_state.goal = value
                go_to_step(4)
    st.divider()
    back_button(3)


# ---------------------------------------------------------------- Step 4

def render_step_details() -> None:
    wizard_header(4, 4, "🧾 Last quick details", "Almost there — this takes 10 seconds.")

    with st.form("details"):
        col_a, col_b = st.columns(2)
        with col_a:
            portions = st.number_input("👥 How many portions?", min_value=1, max_value=14, value=2)
            max_time = st.select_slider("⏱️ How much time do you have?",
                                        options=[15, 30, 45, 60, 90, 120], value=30,
                                        format_func=lambda m: f"{m} min")
            diet_style = st.selectbox("🥦 Any diet style?",
                                      ["normal", "vegetarian", "vegan", "gluten_free", "dairy_free"],
                                      format_func=lambda v: v.replace("_", " ").title())
        with col_b:
            allergies = st.text_input("⚠️ Any allergies? (leave empty if none)",
                                      placeholder="peanuts, dairy, gluten")
            tools = st.multiselect("🍳 What can you cook with?",
                                   ["pan", "pot", "oven", "microwave", "air fryer", "blender"],
                                   default=["pan", "pot", "oven"])
        with st.expander("More options (optional)"):
            gender = st.selectbox("Gender for calorie context", ["none", "male", "female"])
            height_cm = st.number_input("Height cm", min_value=0, max_value=260, value=0)
            weight_kg = st.number_input("Weight kg", min_value=0, max_value=300, value=0)

        submitted = st.form_submit_button("🍽️ Cook up my recipes!", type="primary", width="stretch")

    back_button(4)

    if submitted:
        st.session_state.monitor_events = []
        raw_preferences = {
            "goal": st.session_state.goal or "quick",
            "allergies": [item.strip() for item in allergies.split(",") if item.strip()],
            "diet_style": diet_style,
            "max_cooking_time_minutes": max_time,
            "meals_needed": int(portions),
            "meal_type": st.session_state.meal_type or "dinner",
            "constraint_resolution": "make_best_effort",
            "gender": gender,
            "height_cm": height_cm or None,
            "weight_kg": weight_kg or None,
            "available_tools": tools,
        }

        images = None
        if st.session_state.ingredient_mode == "photo":
            images = st.session_state.uploaded_photos
        elif st.session_state.ingredient_mode == "typed":
            raw_preferences["confirmed_ingredients"] = [
                item.strip()
                for item in re.split(r"[,;\r\n]+", st.session_state.typed_ingredients)
                if item.strip()
            ]
        else:
            raw_preferences["confirmed_ingredients"] = SURPRISE_INGREDIENTS

        st.session_state.last_preferences = raw_preferences
        with st.spinner("👨‍🍳 Cooking up ideas... local model runs can take a minute or two."):
            result = run_fridge_agent_workflow(images, raw_preferences, monitor=add_monitor_event)
        st.session_state.latest_result = result
        st.session_state.latest_result_json = result.model_dump_json(indent=2)
        go_to_step(5)


# ------------------------------------------------------- Recipe refreshing

ADD_INTENT = re.compile(
    r"\b(buy|buying|bought|add|adding|added|getting|got|grab|grabbing|pick(ing)? up|purchase[ds]?)\b",
    re.IGNORECASE,
)


def default_preferences() -> dict:
    return {
        "goal": st.session_state.goal or "quick",
        "allergies": [],
        "diet_style": "normal",
        "max_cooking_time_minutes": 30,
        "meals_needed": 2,
        "meal_type": st.session_state.meal_type or "dinner",
        "constraint_resolution": "make_best_effort",
        "available_tools": ["pan", "pot", "oven"],
    }


def current_ingredient_names() -> list[str]:
    result = st.session_state.latest_result
    if result is not None and result.verified_ingredients.ingredients:
        return [ingredient.name for ingredient in result.verified_ingredients.ingredients]
    return [
        item.strip().lower()
        for item in re.split(r"[,;\r\n]+", st.session_state.typed_ingredients)
        if item.strip()
    ]


def refresh_with_added_products(new_items: list[str]) -> None:
    """Re-run the workflow with the current products plus new ones, updating the cards in place."""
    merged = current_ingredient_names()
    for item in new_items:
        cleaned = item.strip().lower()
        if cleaned and cleaned not in merged:
            merged.append(cleaned)

    preferences = dict(st.session_state.get("last_preferences") or default_preferences())
    preferences["confirmed_ingredients"] = merged
    st.session_state.last_preferences = preferences
    st.session_state.typed_ingredients = ", ".join(merged)
    st.session_state.ingredient_mode = "typed"
    st.session_state.monitor_events = []

    with st.spinner(f"👨‍🍳 Adding {', '.join(new_items)} and refreshing your recipes..."):
        result = run_fridge_agent_workflow(None, preferences, monitor=add_monitor_event)
    st.session_state.latest_result = result
    st.session_state.latest_result_json = result.model_dump_json(indent=2)
    st.session_state.step = 5
    st.rerun()


def extract_added_products(message: str) -> list[str]:
    """Detect 'I'm buying X' style chat messages and pull out the product names."""
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


# ---------------------------------------------------------------- Step 5

def render_results() -> None:
    result = st.session_state.latest_result
    if result is None:
        go_to_step(1)
        return

    st.title("🍽️ Here's what you can make!")

    col_restart, col_retry = st.columns(2)
    with col_restart:
        if st.button("🔄 Start over", width="stretch"):
            st.session_state.latest_result = None
            st.session_state.ingredient_mode = None
            go_to_step(1)
    with col_retry:
        if st.button("🎛️ Same products, different vibe", width="stretch"):
            go_to_step(2)

    with st.container(border=True):
        st.markdown("**🛒 Got something new? Add products and refresh the recipes:**")
        add_col, button_col = st.columns([4, 1])
        new_products_text = add_col.text_input(
            "Add products",
            placeholder="e.g. blended beef, sour cream",
            label_visibility="collapsed",
            key="add_products_input",
        )
        if button_col.button("Refresh 🍽️", type="primary", width="stretch") and new_products_text.strip():
            refresh_with_added_products(
                [item for item in re.split(r"[,;\r\n]+", new_products_text) if item.strip()]
            )

    if not result.final_recipes:
        if not result.verified_ingredients.ingredients:
            st.error("We couldn't figure out your ingredients — the photo detection came back empty.")
            for question in result.verified_ingredients.clarification_questions:
                st.warning(question)
            st.markdown("**Quick fix — just tell me what you've got:**")
            quick_products = st.text_input(
                "Your products", placeholder="e.g. chicken, rice, onion, tomatoes",
                label_visibility="collapsed",
            )
            if quick_products.strip() and st.button("🍳 Cook with these instead", type="primary"):
                preferences = dict(
                    st.session_state.get("last_preferences")
                    or {
                        "goal": st.session_state.goal or "quick",
                        "allergies": [],
                        "diet_style": "normal",
                        "max_cooking_time_minutes": 30,
                        "meals_needed": 2,
                        "meal_type": st.session_state.meal_type or "dinner",
                        "constraint_resolution": "make_best_effort",
                        "available_tools": ["pan", "pot", "oven"],
                    }
                )
                preferences["confirmed_ingredients"] = [
                    item.strip()
                    for item in re.split(r"[,;\r\n]+", quick_products)
                    if item.strip()
                ]
                st.session_state.ingredient_mode = "typed"
                st.session_state.typed_ingredients = quick_products
                st.session_state.monitor_events = []
                with st.spinner("👨‍🍳 Cooking up ideas..."):
                    retry = run_fridge_agent_workflow(None, preferences, monitor=add_monitor_event)
                st.session_state.latest_result = retry
                st.session_state.latest_result_json = retry.model_dump_json(indent=2)
                st.rerun()
        else:
            st.error(
                "No safe recipes fit these constraints. Try more time, fewer portions, "
                "or double-check the allergy list."
            )
        return

    for index, recipe in enumerate(result.final_recipes, start=1):
        with st.container(border=True):
            st.markdown(f"## {index}. {recipe.title}")
            if recipe.description:
                st.markdown(f"*{recipe.description}*")

            chip_cols = st.columns(4)
            chip_cols[0].metric("⏱️ Total", f"{recipe.time_minutes} min")
            chip_cols[1].metric("🔪 Prep", f"{recipe.prep_time_minutes} min")
            chip_cols[2].metric("🍳 Cook", f"{recipe.cook_time_minutes} min")
            chip_cols[3].metric("👥 Portions", recipe.portions)

            st.markdown("**🛒 You already have:** " + ", ".join(recipe.ingredients_used))
            if recipe.missing_ingredients:
                st.markdown("**🧂 You might need:** " + ", ".join(recipe.missing_ingredients))

            if recipe.ingredient_amounts:
                with st.expander("📏 Exact amounts for your portions"):
                    st.table(
                        [
                            {
                                "Ingredient": amount.name,
                                "Per portion": amount.amount_per_portion,
                                f"Total for {recipe.portions}": amount.total_amount,
                            }
                            for amount in recipe.ingredient_amounts
                        ]
                    )

            st.markdown("**👨‍🍳 How to make it:**")
            for step_number, step in enumerate(recipe.steps, start=1):
                st.markdown(f"{step_number}. {step}")

            st.caption(
                f"Roughly {recipe.nutrition.calories} kcal, {recipe.nutrition.protein_g}g protein, "
                f"{recipe.nutrition.carbs_g}g carbs, {recipe.nutrition.fat_g}g fat per portion. "
                "Estimates only, not medical advice."
            )
            if recipe.food_waste_note:
                st.caption(f"♻️ {recipe.food_waste_note}")
            for warning in recipe.safety_warnings:
                st.warning(warning)

    with st.expander("🔍 Behind the scenes (agent workflow)"):
        for event_index, event in enumerate(st.session_state.monitor_events, start=1):
            st.markdown(f"**{event_index}. {event['time']} — {event['agent']}**")
            st.caption(event["message"])
        if st.session_state.latest_result is not None:
            st.json(compact_details(st.session_state.latest_result.model_dump()))

    with st.expander("🕵️ Run Hermes Agent audit"):
        st.caption("Asks the external Hermes Agent CLI to double-check the recipes are actually cookable.")
        if st.button("Run audit"):
            with st.spinner("Auditing the workflow..."):
                audit = run_hermes_agent_audit(result.model_dump())
            st.json(audit)


# ---------------------------------------------------------------- Chat

def build_chat_prompt(user_message: str) -> str:
    context = st.session_state.latest_result_json or "No recipes have been generated yet."
    return f"""
You are FridgeAgent's friendly cooking chat assistant.
Answer the user's question using the current recipe workflow context when relevant.
Be practical, brief, warm, and allergy-conscious. Plain language, no jargon. No medical claims.

Current workflow context:
{context}

User question:
{user_message}
"""


def render_chat() -> None:
    st.divider()
    st.subheader("💬 Questions? Ask away")
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    chat_message = st.chat_input("Substitutions, swaps... or say what you're buying and I'll refresh the recipes")
    if chat_message:
        st.session_state.chat_messages.append({"role": "user", "content": chat_message})
        with st.chat_message("user"):
            st.markdown(chat_message)

        added_products = extract_added_products(chat_message)
        if added_products:
            reply = (
                f"🛒 Nice — adding **{', '.join(added_products)}** to your products "
                "and refreshing the recipes above!"
            )
            with st.chat_message("assistant"):
                st.markdown(reply)
            st.session_state.chat_messages.append({"role": "assistant", "content": reply})
            refresh_with_added_products(added_products)
        else:
            with st.chat_message("assistant"):
                try:
                    answer = GemmaClient().generate_text(build_chat_prompt(chat_message))
                except RuntimeError as exc:
                    answer = str(exc)
                st.markdown(answer)
            st.session_state.chat_messages.append({"role": "assistant", "content": answer})


# ---------------------------------------------------------------- Main

st.set_page_config(page_title="FridgeAgent", page_icon="🍳", layout="wide")
init_state()

with st.sidebar:
    st.subheader("⚙️ Model status")
    st.caption(f"Mode: `{os.environ['APP_MODE']}`")
    if os.environ["APP_MODE"] == "local":
        st.caption(f"Model: `{os.environ['GEMMA_MODEL_NAME']}` via Ollama")
    if st.button("Test model connection"):
        try:
            st.success(GemmaClient().health_check())
        except RuntimeError as exc:
            st.error(str(exc))
    if st.button("Reset everything"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

step = st.session_state.step
if step == 1:
    render_step_ingredients()
elif step == 2:
    render_step_meal()
elif step == 3:
    render_step_goal()
elif step == 4:
    render_step_details()
else:
    render_results()

if st.session_state.latest_result is not None and step == 5:
    render_chat()
