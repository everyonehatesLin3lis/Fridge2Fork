# FridgeAgent

FridgeAgent is a multi-agent Gemma 4 assistant that turns fridge photos into practical recipes.

It helps a user upload up to five fridge or food photos, review detected ingredients, add cooking goals and constraints, then generate realistic recipe cards that minimize missing ingredients and reduce food waste.

FridgeAgent is not one big recipe prompt. It is a four-agent workflow where each Gemma-powered agent handles a bounded part of the cooking decision process: vision and ingredient verification, user constraints, RAG-grounded recipe planning with portion math and rough nutrition, and final safety-checked recipe writing.

## Why Gemma 4

Gemma 4 fits this project because the task is naturally multimodal and constraint-heavy. The system needs to understand a fridge image, turn visible food into structured ingredients, reason over allergies and cooking goals, and produce practical recipes with minimal missing items.

In local testing, the current model was useful for orchestration and structured
recipe generation, but it did not always produce enough recipe variety on its
own. To improve creativity without making the app uncontrolled, FridgeAgent uses
the Kaggle recipe dataset as a reference database through local RAG. Gemma still
plans the final user-specific recipe, but it can now ground ideas in retrieved
recipe patterns instead of repeating the same small set of meals.

The current recipe output also puts extra emphasis on measurable execution:
ingredient amounts per portion, total product needed for the requested portions,
prep time, cook time, total time, and concrete cooking steps. Recipes should say
how to cut ingredients, what heat or cooking environment to use, how long each
stage takes, and how to recognize doneness.

## One-Command Start

Double-click `run.bat` (or run `python run.py`). It automates the whole startup
chain — no other terminal commands are needed:

1. Creates the virtual environment on first run and installs dependencies when
   `requirements.txt` changed.
2. Reads `.env` (if present) for the model mode.
3. For local mode it starts Ollama automatically if it is not running and pulls
   the model on first use.
4. If no model backend is available it falls back to mock mode so the app
   always starts, then launches the webapp in your browser.

Optional flags: `run.bat --mock`, `run.bat --google`, `run.bat --local`.

## Manual Setup

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Copy `.env.example` to `.env` for live model settings. The app defaults to `APP_MODE=mock`, so it can run without API keys.

## Local Gemma 4 Run

Install and start Ollama, then make sure the local model is available:

```powershell
ollama serve
ollama run gemma4:e4b
```

Run the local deployment entrypoint:

```powershell
.\.venv\Scripts\streamlit.exe run main.py
```

`main.py` defaults to:

```env
APP_MODE=local
GEMMA_MODEL_NAME=gemma4:e4b
OLLAMA_BASE_URL=http://localhost:11434
```

## Mock And Live Modes

- `APP_MODE=mock`: deterministic text/demo flow, no paid API calls. Mock mode does not inspect uploaded images; type confirmed ingredients for demos.
- `APP_MODE=local`: calls a local Ollama-compatible model through `src/services/gemma_client.py`.
- `APP_MODE=google`: calls the real Google AI (Gemini) API through the `google-genai` SDK. Set `GOOGLE_API_KEY` (from [aistudio.google.com/apikey](https://aistudio.google.com/apikey)) and optionally `GOOGLE_MODEL_NAME` (default `gemini-2.0-flash`). Works without any local model install, including image ingredient detection.
- `APP_MODE=live`: routes calls through `src/services/gemma_client.py`. Provider-specific API wiring can be added there without touching agent files.

## Recipe RAG

The Recipe Planner can use a small local search index built from the Kaggle
dataset `wilmerarltstrmberg/recipe-dataset-over-2m`. Download and index it with:

```powershell
.\.venv\Scripts\python.exe scripts\download_recipe_dataset.py
.\.venv\Scripts\python.exe scripts\build_recipe_rag_index.py --dataset-path "PATH_PRINTED_BY_DOWNLOAD" --limit 25000
```

The index is stored at `data/recipe_rag_index.jsonl` and is ignored by Git. When
present, Gemma receives a few retrieved recipe references for cooking patterns,
timing, and ingredient combinations before it plans user-specific portions.

For speed, FridgeAgent does not load the full 2M+ recipe dataset into Streamlit
at runtime. The build script creates a compact local JSONL index sample, and the
Recipe Planner searches only a few relevant references per run. This keeps
recipe grounding useful without slowing down the interactive demo.

## Architecture

```text
Fridge photo -> Hermes -> Vision Agent
-> Hermes -> Constraints Agent
-> Hermes -> Recipe Planner Agent
-> Hermes -> Final Recipe Agent
-> Recipe cards
-> optional Hermes Agent audit
```

Hermes is the deterministic message-passing layer in `src/orchestration/hermes.py`.
It does not identify food or write recipes. It enforces a fixed four-stage order,
prevents repeated stages, builds clean handoff payloads, and stores a debug trace
so the multi-agent flow is visible in tests and Streamlit output.

This project uses Hermes as a strict local orchestration layer, not as another
LLM agent. That improved speed and reliability because the app no longer asks a
model to decide every handoff. Hermes runs in Python, keeps the workflow bounded
to four stages, prevents loops, and passes only the structured data each stage
needs.

The four specialist agents are:

- `vision_agent`: detects visible ingredients across up to five uploaded photos, merges duplicate detections, normalizes names, flags uncertainty, and prepares verified ingredients.
- `constraints_agent`: validates user goals, allergies, diet, portions, cooking time, and tools.
- `recipe_planner_agent`: searches the local recipe RAG index, plans recipes, calculates per-portion and total amounts, runs a feasibility check, repairs unrealistic dish drafts, writes concrete cooking steps, and ranks rough nutrition fit.
- `final_recipe_agent`: filters unsafe recipes, adds allergy warnings, and writes final recipe cards.

## Hermes Agent Audit Layer

For the Hermes Agent Challenge, FridgeAgent includes an optional external audit
layer that calls the real Nous Research Hermes Agent CLI:

```powershell
hermes chat -Q -q "<recipe audit prompt>"
```

The audit prompt is built from:

- `hermes/fridge2fork_context.md`
- `hermes/cooking_feasibility_rules.md`
- `hermes/recipe_audit_task.md`
- the generated FridgeAgent workflow JSON

Hermes Agent reviews whether the generated recipe can actually be cooked. It
checks ingredient roles, missing binders or bases, allergy risks, portion math,
measurement rows, and cooking feasibility. This is separate from the in-app
`HermesOrchestrator`: the orchestrator controls handoffs, while Hermes Agent is
used as an external agentic critic and tool-driven audit layer.

Run the audit manually with:

```powershell
.\.venv\Scripts\python.exe scripts\hermes_recipe_audit.py --input data\sample_outputs\eight_ingredient_debug.json
```

If the `hermes` CLI is not installed or configured, the script returns setup
guidance plus a deterministic fallback audit so the app remains usable.

## LLM Telemetry And Ops Report

The app automatically collects lightweight LLM engineering telemetry while it
runs (no extra setup, files are git-ignored):

- `data/telemetry/vision_detection.jsonl`: one row per analyzed photo with
  model latency, JSON parse success, ingredient count, and confidence
  min/mean/max, so vision quality can be tracked over time.
- `data/telemetry/rag_retrieval.jsonl`: one row per recipe reference search
  with retrieval latency, result count, and top score, so RAG performance and
  hit rate are measurable.

Summarize everything that has been collected:

```powershell
.\.venv\Scripts\python.exe scripts\llm_ops_report.py
```

Add `--check` to fail (exit code 1) when performance budgets are violated —
this is what CI runs on every push.

## CI

`.github/workflows/ci.yml` runs on every push and pull request:

1. the full pytest suite in mock mode, including RAG retrieval correctness and
   a retrieval latency budget against a committed fixture index, and
2. `scripts/llm_ops_report.py --check`, which enforces the RAG latency and
   vision parse-success budgets over telemetry collected during the CI run.

Telemetry produced during CI is uploaded as a build artifact so retrieval
performance can be compared between commits.

## Tests

```powershell
pytest
```

## Troubleshooting

### Local Gemma Timeout

If Streamlit shows a traceback ending with:

```text
TimeoutError: timed out
...
src/services/gemma_client.py
with urlopen(request, timeout=120) as response
```

the app reached Ollama, but the local model did not finish before the client timeout. This is more likely with large images, long prompts, many portions, or a slower CPU/GPU.

Try:

```powershell
ollama list
ollama ps
```

Then restart the app and use fewer typed ingredients or skip the image for a quick test:

```powershell
Get-Process streamlit,python -ErrorAction SilentlyContinue | Stop-Process -Force
.\.venv\Scripts\streamlit.exe run main.py
```

The code catches local Gemma timeouts and lets agents fall back where possible, so a slow model should not crash the whole workflow.

### Low-Confidence Vision Detections

The Vision Agent can struggle with unclear packaging, labels, and product variants. For example, a carton may be cow milk, almond milk, oat milk, or lactose-free milk, which matters for allergies, diet style, and nutrition.

Current rule:

- Ingredients with confidence below `0.5` are not sent directly to recipe planning.
- They are collected as low-confidence items.
- The app asks the user to confirm what those products are.
- Confirmed typed ingredients override uncertain photo detections.

This keeps the app from treating uncertain visual guesses as safe cooking facts.

## Limitations

- Nutrition values are rough estimates, not medical advice.
- Mock image detection uses fixed demo ingredients.
- Live Gemma API transport is centralized but intentionally provider-light for the MVP.

## Future Improvements

- Add real Gemma 4 multimodal provider integration.
- Add sample screenshots and a demo GIF.
- Add a small library of evaluation images and expected outputs.
