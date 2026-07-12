# 🍳 FridgeAgent

**A fridge-to-recipe assistant for people who love food too much to waste it.**

Snap photos of your fridge, answer three friendly questions, and a four-agent AI
workflow turns what you actually have into real, cookable recipes — with exact
amounts for your portions and steps a tired human can follow at 9pm.

Built up for the [DEV Weekend Challenge: Passion Edition](https://dev.to/challenges/weekend-2026-07-09).
Our take on passion: the everyday kind — loving food enough to cook with what
you've got instead of letting it expire.

## Run It (One Command)

Double-click **`run.bat`**. That's the whole setup:

1. Creates the virtual environment and installs dependencies (only when
   `requirements.txt` changed).
2. Starts Ollama in the background if it isn't running; pulls the models on
   first use.
3. Falls back to Google Gemini (if `GOOGLE_API_KEY` is set) or mock mode when
   no local model is available — the app always starts.
4. Opens the wizard in your browser.

Optional: `run.bat --mock`, `run.bat --google`, `run.bat --local`.

## The Flow

1. **"Sup! What are we cooking with today?"** — 📷 snap your fridge, ⌨️ type
   your products, or 🎲 skip and cook with staples
2. **"What's the occasion?"** — breakfast / lunch / dinner / snacks / meal prep
3. **"What are you craving?"** — quick & easy / healthy / high protein / budget / comfort food
4. Ten seconds of details → **recipe cards**: description, time chips,
   "you already have / you might need", numbered plain-language steps
5. Tell the chat *"I'm buying blended beef"* → the cards refresh in place with
   recipes built around blended beef. Or hit **🎲 Show me different recipes**
   for a fresh batch from the same fridge.

---

## The Journey

This project was rebuilt over one weekend, and almost nothing went according to
plan. Here's what actually happened — the bugs, the evidence, and the fixes —
because the debugging turned out to be the most interesting part.

### Chapter 1: "Nothing happens"

First real test: pick ingredients, click **Generate recipes**... nothing.
No error, no recipes, no clue.

It turned out to be *three* stacked problems:

- **Results vanished on rerun.** Recipe cards only rendered during the submit
  event; any later interaction re-ran the Streamlit script and wiped them.
  Fix: results live in `session_state` and render on every run.
- **The debug monitor was killing the run.** Our live agent-trace panel
  re-sent full RAG dumps and model outputs over the websocket on *every*
  workflow event. Big payloads froze the browser tab, the websocket dropped,
  and Streamlit silently killed the script mid-workflow — recipes were being
  generated and thrown away. Fix: monitor payloads are compacted (capped
  lists, truncated strings); full data stays in the "Agent outputs" expander.
- **Timeouts pretending to be results.** Local model calls were capped at a
  hardcoded 120s while photo analysis alone measured ~63s. The timeout was
  caught, swallowed, and surfaced as "zero ingredients found". Fix:
  `OLLAMA_TIMEOUT_SECONDS` (default 300) and a loud, specific error state in
  the UI with an inline "type your products instead" recovery box.

**Lesson:** a silent failure path is a lie you tell your future self.

### Chapter 2: The photos that died between steps

With the wizard UI, users pick photos on step 1 and generate on step 4.
Detection kept coming back empty — and telemetry (see below) showed why:

```json
{"image_bytes": 0, "latency_ms": 11036, "raw_response_chars": 60, "ingredient_count": 0}
```

Zero image bytes. Streamlit frees uploaded file data the moment the uploader
widget leaves the screen — so by step 4, the photos were gone and the model was
politely analyzing *nothing*. Fix: copy the raw bytes into session state the
moment photos are picked ("N photo(s) locked in ✅").

**Lesson:** know your framework's widget lifecycle before building a wizard on it.

### Chapter 3: The model that hallucinated a fridge

The scariest bug, because it looked like success. Early on, photo detection
returned a lovely list: milk, eggs, butter, deli meat... Except those weren't
in the photo. The telemetry made the pattern obvious:

| | Real analysis | Our runs |
|---|---|---|
| Latency | ~63s | 11–26s |
| Response size | ~2,700 chars | 60–200 chars |
| Detections | 8 items | 0 items (or invented ones) |

Direct API tests confirmed it: `gemma4:e4b`'s vision path in Ollama decodes the
image (the server logs literally say `image decoded in 93ms`) but the
embeddings never reach the language model, which answers "no image provided" —
or worse, **invents a statistically plausible fridge**. Re-pulling the model
didn't help; no Ollama update was available.

The fix that worked, verified on 8 real test photos (0/8 detected before, **8/8 after**, 5–12s each):

- **A dedicated vision model** — `VISION_MODEL_NAME=llava:7b` handles photos
  while `gemma4:e4b` keeps writing recipes (it's genuinely good at that).
  `run.bat` pulls it automatically.
- **`format=json`** — Ollama constrains the output to valid JSON, because
  vision models freestyle otherwise.
- **A tolerant parser** — a 7B vision model will not fill a deeply nested
  schema. The prompt asks for a flat shape and the parser fills in
  category/quantity/confidence defaults, instead of throwing away a correct
  answer because it came in the wrong outfit.

**Lesson:** "the model returned something" is not the same as "the model saw
your image". Log enough to tell the difference.

### Chapter 4: The same two recipes, forever

Refreshing with the same ingredients produced the same recipes — technically
correct, emotionally deflating. And newly added products ("I'm buying blended
beef!") got tossed into the ingredient pool and promptly ignored.

Fixes:

- The planner runs in **creative mode** (temperature 0.95 + random seed), so
  identical inputs stop producing identical outputs.
- Every refresh passes the **previously shown titles** back with an explicit
  *"do not repeat these — change technique or cuisine"* instruction.
- Added products are marked **must-use**: *"every recipe MUST use them as a
  central ingredient, not a garnish"*, and they lead the ingredient list so
  even the deterministic fallback recipes anchor on them.

Verified live: pasta/eggs/parmesan/onion gave *"Creamy Onion & Parmesan Pasta
Scramble"* and *"Cheesy Onion Pasta Bake"*; refreshing with blended beef gave
*"Inside Out Ravioli Skillet"* and *"Blended Beef Bowl"* — no repeats, beef
front and center in both.

### What kept us honest: telemetry

Every one of these bugs was found or confirmed with a tiny LLM-ops layer the
app runs automatically (git-ignored JSONL, no setup):

- `data/telemetry/vision_detection.jsonl` — per photo: latency, image bytes,
  JSON parse success, ingredient count, confidence min/mean/max
- `data/telemetry/rag_retrieval.jsonl` — per search: latency, index size, hit
  count, top score

Three ways to look at it:

1. **📊 LLM Ops panel** in the app sidebar (live summaries)
2. `python scripts/llm_ops_report.py --check` — full report; exits non-zero
   when performance budgets are violated
3. **CI** (`.github/workflows/ci.yml`) — every push runs the 51-test suite
   (including RAG correctness + latency budget against a committed fixture
   index) plus the budget check, and uploads the run's telemetry as an
   artifact so retrieval performance is comparable between commits

---

## Under the Hood

```text
Photos / typed products
   -> Vision Agent        (detect, merge, flag low-confidence for confirmation)
   -> Constraints Agent   (portions, time, allergies, diet, tools)
   -> Recipe Planner      (RAG retrieval, portion math, feasibility repair)
   -> Final Recipe Agent  (allergen filtering, final cards)
   -> Recipe cards + optional external Hermes Agent audit
```

Handoffs are controlled by `HermesOrchestrator` — a deterministic Python
message-passing layer, not another LLM. It enforces a fixed four-stage order,
prevents loops, and keeps a trace you can inspect in the "Behind the scenes"
expander. One hard rule: **if no ingredients can be verified, the pipeline
stops** — the planner is never allowed to invent what's in your fridge.

Safety details we care about: ingredients detected below 0.5 confidence are
never cooked with silently — the app asks you to confirm them ("possibly
chicken (0.30)" becomes a question, not a dinner). Allergen conflicts remove
recipes entirely, and packaged-ingredient warnings are added for hidden
allergens.

**Recipe RAG:** the planner grounds its ideas in a compact local index sampled
from the Kaggle `recipe-dataset-over-2m` dataset (~25k records, lexical
scoring, ~0.8s mean retrieval). Build it with:

```powershell
.\.venv\Scripts\python.exe scripts\download_recipe_dataset.py
.\.venv\Scripts\python.exe scripts\build_recipe_rag_index.py --dataset-path "PATH_PRINTED_BY_DOWNLOAD" --limit 25000
```

The app works without the index — recipes are just less varied.

## Modes

| Mode | What it does |
|---|---|
| `APP_MODE=local` (default) | Recipes via `GEMMA_MODEL_NAME` (`gemma4:e4b`), photos via `VISION_MODEL_NAME` (`llava:7b`), both through Ollama |
| `APP_MODE=google` | Everything through the real Gemini API (`google-genai` SDK, default `gemini-2.0-flash`). Free key from [aistudio.google.com/apikey](https://aistudio.google.com/apikey). No local GPU needed |
| `APP_MODE=mock` | Deterministic demo flow, no model calls at all |

Copy `.env.example` to `.env` to configure. Manual start, if you prefer it over
`run.bat`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run main.py
```

## Tests

```powershell
pytest
```

51 tests: agent workflow in mock mode, RAG retrieval correctness and latency
budgets, telemetry collection, Google AI client, JSON parsing edge cases.

## Limitations

- Nutrition values are rough estimates, not medical advice.
- Local photo analysis takes ~5–12s per photo; local recipe generation ~60–90s.
- The RAG index is a compact sample for speed, not the full 2M-recipe dataset.
- Mock mode cannot inspect images — type your products instead.

## Disclosure

The four-agent core (vision, constraints, planner, final recipe writer)
predates the Passion Edition challenge and was originally built for an earlier
challenge. The challenge-weekend work: the four-step wizard UI, the
one-command launcher, the LLM telemetry + ops report + CI pipeline, the entire
vision debugging saga and dedicated-vision-model fix, recipe variety on
refresh, must-use added products, chat-triggered recipe refreshes, and the
Google AI provider.
