---
title: "FridgeAgent: Less Thinking, More Cooking"
published: false
description: "A four-agent AI cooking assistant that handles the meal-idea thinking and turns fridge photos into practical, allergy-aware recipes."
tags: weekendchallenge, devchallenge, ai, googleai
cover_image: https://raw.githubusercontent.com/everyonehatesLin3lis/Fridge2Fork/main/screenshots/01_welcome.png
---

*This is a submission for [Weekend Challenge: Passion Edition](https://dev.to/challenges/weekend-2026-07-09).*

## What I Built

**FridgeAgent** is a fridge-to-recipe assistant that saves the time and mental
effort spent deciding what to cook.

You snap up to five photos of your fridge (or just type what you've got), answer
three friendly questions — *what's the occasion? what are you craving? how much
time do you have?* — and a four-agent AI workflow turns whatever is actually in
your kitchen into real, cookable recipe cards: appetizing one-line
descriptions, "you already have / you might need" ingredient splits, exact
amounts for the requested portions, **estimated calories per portion**, and
numbered plain-language steps a tired person can follow at 9pm.

My interpretation of **passion** is loving the cooking, not the deciding. The
best part of a meal is the pan hitting the stove — not twenty minutes spent
staring into the fridge and trying to invent an idea. FridgeAgent handles that
idea work in minutes, so your time and energy go into the part you actually
love.

Everything runs **locally** — the whole thing boots with one double-click of `run.bat`, which sets up the environment, starts Ollama, pulls the models, and opens the app. No cloud required (though there's an optional Gemini mode, see below).

## Demo

![FridgeAgent welcome screen](https://raw.githubusercontent.com/everyonehatesLin3lis/Fridge2Fork/main/screenshots/01_welcome.png)

![Choose the occasion](https://raw.githubusercontent.com/everyonehatesLin3lis/Fridge2Fork/main/screenshots/03_occasion.png)

![Recipe cards with estimated calories per portion](https://raw.githubusercontent.com/everyonehatesLin3lis/Fridge2Fork/main/screenshots/07_recipes_full.png)

The flow in 30 seconds:

1. **"Sup! What are we cooking with today?"** → 📷 snap my fridge / ⌨️ type my products / 🎲 surprise me
2. **"What's the occasion?"** → breakfast / lunch / dinner / snacks / meal prep — one click
3. **"What are you craving?"** → quick & easy / healthy / high protein / budget / comfort food
4. Ten seconds of details (portions, time, allergies, tools) → **recipe cards
   with estimated kcal per portion**
5. Tell the chat *"I will buy blended beef"* → the cards **refresh in place** with new recipes built around blended beef
6. Hit **🎲 Show me different recipes** any time you want fresh ideas from the same fridge

## Code

{% github everyonehatesLin3lis/Fridge2Fork %}

Repository: [github.com/everyonehatesLin3lis/Fridge2Fork](https://github.com/everyonehatesLin3lis/Fridge2Fork)

**Disclosure:** the four-agent core (vision → constraints → planner → final
recipe writer) predates this challenge — it was originally built for an earlier
challenge submission. The challenge-weekend work includes the redesigned
wizard UI, one-command launcher, LLM telemetry and CI pipeline, local vision
fix, recipe variety on refresh, chat-triggered recipe refreshes, Google AI
provider, new decision-time positioning, calories-per-portion recipe cards,
and the refreshed documentation and screenshots.

## How I Built It

**Stack:** Python, Streamlit, Pydantic, Ollama (`gemma4:e4b` for recipe generation + `llava:7b` for photo analysis), a local lexical RAG index sampled from a 2M-recipe Kaggle dataset, and the `google-genai` SDK for the optional Gemini mode.

The architecture is four specialist agents behind a deterministic orchestrator (no LLM deciding handoffs — the workflow is bounded and loop-free by construction):

1. **Vision Agent** — detects ingredients across up to 5 photos, merges duplicates, flags low-confidence items for user confirmation instead of cooking with guesses
2. **Constraints Agent** — validates portions, time, allergies, diet, tools
3. **Recipe Planner** — retrieves grounding references from the local RAG index, plans recipes with portion math, runs a feasibility check that repairs uncookable drafts
4. **Final Recipe Agent** — filters allergen conflicts and writes the final cards

Hermes is the deterministic orchestrator, not a fifth agent. Each handoff is
recorded for inspection, but routing itself adds no model calls and cannot loop.

The most interesting decisions came from things going wrong:

- **My local model was hallucinating fridges.** Photo detection "worked" — until telemetry showed a real analysis takes 60s/2,700 chars and mine took 11s/60 chars. The model wasn't seeing images at all; it was *inventing plausible fridge contents*. Ollama's logs said "image decoded in 93ms" while the model said "no image provided." The fix: a dedicated vision model (`llava:7b`) for photos while gemma4 keeps writing recipes, `format=json` forcing, and a tolerant parser — because a 7B vision model will not fill your beautiful nested schema, and pretending otherwise means 0/8 photos detected instead of 8/8.
- **The "nothing happens" bug.** The live agent-trace panel was shipping full RAG dumps over the websocket on every event, freezing the browser tab, dropping the connection — and Streamlit silently kills the script when that happens. Recipes were being generated and thrown away. Lesson: debug UIs need payload budgets too.
- **Measure, don't vibe.** Every photo analysis and every RAG search now logs latency, parse success, and confidence stats to JSONL. There's an 📊 LLM Ops panel in the sidebar, a CLI report with performance budgets, and CI fails the build if RAG retrieval blows its latency budget. This telemetry is literally how the vision bug was found.

The full war-story version with evidence is in the [README](https://github.com/everyonehatesLin3lis/Fridge2Fork#the-journey).

## What I Learned

- A successful model response does not prove the model saw the image. Record
  image bytes, latency, parsing success, and confidence so failures are
  distinguishable from empty results.
- Multi-agent does not have to mean model-driven routing. A deterministic
  orchestrator is faster, bounded, and easier to debug for a fixed workflow.
- Recipe usefulness is in the details: portion-aware amounts, realistic time,
  doneness checks, allergy filtering, and a visible rough calorie estimate are
  more valuable than another paragraph of creative prose.

## Prize Categories

**Best Use of Google AI** — FridgeAgent has a first-class Gemini mode (`APP_MODE=google` via the `google-genai` SDK): set a free API key from AI Studio and both photo ingredient detection and recipe generation route through `gemini-2.0-flash` instead of local models — same four-agent workflow, no local GPU needed. It's also the automatic fallback the launcher picks when Ollama isn't installed.

## Validation

- 52 automated tests pass.
- The complete browser flow was verified in mock mode from ingredient entry to
  final recipe cards.
- A repository-wide search confirms the retired positioning no longer appears
  in tracked text.
- The recipe schema, planner prompt, sample output, UI, README, and screenshots
  all use the same current product story.

## Limitations

- Nutrition is deliberately rough and labeled as an estimate; this is not a
  medical or dietary-planning tool.
- Local photo analysis and recipe generation depend on the user's hardware and
  may take about 5–12 seconds per photo and 60–90 seconds for recipe generation.
- The compact RAG index is optional and is not committed because of its size.
- Mock mode cannot inspect photos, so typed ingredients are used for the
  no-model demo path.

## What's Next

- Add an optional sourced nutrition dataset while preserving clear estimate
  labels.
- Make ambiguous image detections easier to confirm before planning.
- Ship a small starter RAG index for better first-run variety.
- Record a short demo video using the included 30-second script.

<!-- Thanks for participating! -->
