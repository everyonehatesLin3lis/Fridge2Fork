# CODEX.md

## Project: FridgeAgent

FridgeAgent is a multi-agent Gemma 4 application for the DEV Gemma 4 Challenge.

Current implementation note: FridgeAgent now uses exactly 4 specialist agents:
`vision_agent`, `constraints_agent`, `recipe_planner_agent`, and
`final_recipe_agent`. Hermes remains a deterministic orchestration layer and is
not counted as a specialist agent. Older seven-agent examples in this planning
document are retained as historical scaffolding, but the active project
architecture is the 4-agent workflow.

The app helps users decide what to cook from food they already have. A user uploads a fridge or food photo, the system detects visible ingredients, asks for cooking goals and constraints, then generates practical recipes that minimize missing ingredients and reduce food waste.

## Challenge Goal

Build a useful, creative application where Gemma 4 does real work at the center of the project.

The submission should clearly show:

- Why Gemma 4 was selected
- How multimodal input is used
- How the multi-agent flow works
- Why the app is useful
- How the implementation can be run and tested
- What is original in this project

## MVP Scope

Build the smallest complete version first.

Required MVP flow:

1. User uploads a fridge or food photo.
2. Vision Ingredient Agent detects visible food items.
3. Ingredient Verification Agent cleans the list and flags uncertainty.
4. User confirms or edits detected ingredients.
5. User fills a short preference form.
6. Recipe Planner Agent creates recipe candidates.
7. Nutrition Goal Agent ranks recipes based on user goals.
8. Allergy Safety Agent checks unsafe ingredients.
9. Final Recipe Writer Agent produces recipe cards.
10. Streamlit displays the final result.

Do not build login, payments, mobile app, barcode scanning, complex meal tracking, or a large nutrition database for the MVP.

## Recommended Tech Stack

Use a simple Python-first stack.

- Python
- Streamlit for UI
- Pydantic for schemas and validation
- Gemma 4 API or local Gemma 4 client wrapper
- SQLite only if saved sessions are needed
- pytest for tests
- python-dotenv for environment variables

Prefer simple readable code over complex abstractions.

## Repository Structure

```text
fridgeagent-gemma/
│
├── README.md
├── LICENSE
├── .env.example
├── .gitignore
├── CODEX.md
├── AGENTS.md
├── requirements.txt
├── app.py
│
├── src/
│   ├── config.py
│   ├── orchestrator.py
│   │
│   ├── agents/
│   │   ├── vision_ingredient_agent.py
│   │   ├── ingredient_verification_agent.py
│   │   ├── user_preference_agent.py
│   │   ├── recipe_planner_agent.py
│   │   ├── nutrition_goal_agent.py
│   │   ├── allergy_safety_agent.py
│   │   └── final_recipe_writer_agent.py
│   │
│   ├── schemas/
│   │   ├── ingredient_schema.py
│   │   ├── preference_schema.py
│   │   ├── recipe_schema.py
│   │   └── agent_state_schema.py
│   │
│   ├── services/
│   │   ├── gemma_client.py
│   │   ├── image_loader.py
│   │   └── json_parser.py
│   │
│   ├── prompts/
│   │   ├── vision_ingredient_prompt.txt
│   │   ├── verification_prompt.txt
│   │   ├── preference_prompt.txt
│   │   ├── recipe_planner_prompt.txt
│   │   ├── nutrition_prompt.txt
│   │   ├── allergy_safety_prompt.txt
│   │   └── final_writer_prompt.txt
│   │
│   └── utils/
│       ├── validators.py
│       └── formatting.py
│
├── tests/
│   ├── test_schemas.py
│   ├── test_orchestrator.py
│   ├── test_allergy_safety.py
│   └── test_json_parser.py
│
├── data/
│   ├── sample_images/
│   └── sample_outputs/
│
├── evals/
│   ├── manual_test_cases.md
│   ├── agent_eval_checklist.md
│   └── example_runs.md
│
└── submission/
    ├── dev_post_draft.md
    ├── demo_script.md
    └── screenshots/
```

## Important Note for Codex

OpenAI Codex automatically reads `AGENTS.md` files as project instructions.

If this file is named `CODEX.md`, also create a duplicate or short wrapper called `AGENTS.md` in the repository root so Codex loads the instructions automatically.

Recommended `AGENTS.md` content:

```md
# AGENTS.md

Read CODEX.md before making changes.

Follow the project scope, architecture, coding rules, and definition of done in CODEX.md.
Keep the application MVP-focused and do not add unnecessary features.
```

## Multi-Agent Architecture

The project should not be implemented as one giant prompt.

Use a clear orchestrated workflow with specialized agents.

```text
Fridge photo
   ↓
Vision Ingredient Agent
   ↓
Ingredient Verification Agent
   ↓
User confirmation
   ↓
User Preference Agent
   ↓
Recipe Planner Agent
   ↓
Nutrition Goal Agent
   ↓
Allergy Safety Agent
   ↓
Final Recipe Writer Agent
   ↓
Recipe cards
```

## Agent Responsibilities

### 1. Vision Ingredient Agent

Input:

- Fridge or food image

Output:

- Structured list of visible ingredients

Responsibilities:

- Detect visible food items
- Estimate quantity only when visible
- Assign confidence scores
- Mark uncertain items
- Avoid pretending uncertain items are certain

Expected output example:

```json
{
  "ingredients": [
    {
      "name": "eggs",
      "category": "protein",
      "quantity": "6",
      "confidence": 0.92,
      "use_soon": false
    },
    {
      "name": "spinach",
      "category": "vegetable",
      "quantity": "1 bag",
      "confidence": 0.78,
      "use_soon": true
    }
  ],
  "uncertain_items": [
    "white container on top shelf"
  ]
}
```

### 2. Ingredient Verification Agent

Input:

- Raw ingredient detection output

Output:

- Cleaned ingredient list
- Clarification questions if needed

Responsibilities:

- Remove duplicates
- Normalize ingredient names
- Flag uncertain items
- Ask only useful clarification questions
- Prepare ingredient list for recipe planning

Example clarification:

```text
I detected a white container. Is it Greek yogurt, sour cream, cream cheese, or something else?
```

### 3. User Preference Agent

Input:

- User form answers

Output:

- Structured user preferences

Responsibilities:

- Normalize goal, allergies, diet style, cooking time, number of meals, and available tools
- Keep height and weight optional
- Do not provide medical advice
- Treat nutrition as rough estimation only

Expected output example:

```json
{
  "goal": "high_protein",
  "allergies": ["peanuts"],
  "diet_style": "normal",
  "max_cooking_time_minutes": 25,
  "meals_needed": 2,
  "height_cm": 190,
  "weight_kg": 86,
  "available_tools": ["pan", "oven"]
}
```

### 4. Recipe Planner Agent

Input:

- Verified ingredients
- Structured preferences

Output:

- Recipe candidates

Responsibilities:

- Generate 2 to 4 recipe candidates
- Use as many available ingredients as practical
- Minimize missing ingredients
- Respect time limit
- Prefer realistic home cooking
- Include food-waste logic when possible

### 5. Nutrition Goal Agent

Input:

- Recipe candidates
- User goal

Output:

- Ranked recipes with rough nutrition estimates

Responsibilities:

- Rank recipes by goal fit
- Estimate calories, protein, carbs, and fats roughly
- Explain why each recipe fits or does not fit the goal
- Clearly label nutrition numbers as estimates

### 6. Allergy Safety Agent

Input:

- Ranked recipes
- User allergies

Output:

- Safe recipes only
- Warnings where needed

Responsibilities:

- Remove recipes containing user-declared allergens
- Warn about possible hidden allergens
- Never suggest a recipe that directly conflicts with an allergy
- Be conservative when uncertain

### 7. Final Recipe Writer Agent

Input:

- Safe ranked recipes

Output:

- User-facing recipe cards

Responsibilities:

- Write clean recipe cards
- Include title, time, ingredients used, missing ingredients, steps, nutrition estimate, goal fit, and food-waste note
- Keep the result practical and readable

## Orchestrator Requirements

The orchestrator controls the workflow.

Create `src/orchestrator.py` with a function similar to:

```python
def run_fridge_agent_workflow(image, raw_user_preferences):
    detected_ingredients = vision_ingredient_agent.run(image)

    verified_ingredients = ingredient_verification_agent.run(
        detected_ingredients
    )

    normalized_preferences = user_preference_agent.run(
        raw_user_preferences
    )

    recipe_candidates = recipe_planner_agent.run(
        ingredients=verified_ingredients,
        preferences=normalized_preferences
    )

    ranked_recipes = nutrition_goal_agent.run(
        recipes=recipe_candidates,
        preferences=normalized_preferences
    )

    safe_recipes = allergy_safety_agent.run(
        recipes=ranked_recipes,
        allergies=normalized_preferences.allergies
    )

    final_output = final_recipe_writer_agent.run(
        safe_recipes=safe_recipes
    )

    return final_output
```

The exact implementation can differ, but the final project should clearly preserve this multi-agent separation.

## Streamlit UI Requirements

Use Streamlit for a fast challenge-ready interface.

Required UI sections:

1. App title and short explanation
2. Image upload
3. Detected ingredient review
4. Preference form
5. Generate recipes button
6. Recipe cards
7. Optional debug expander showing agent outputs

Recommended app title:

```text
FridgeAgent
A multi-agent Gemma 4 assistant that turns fridge photos into practical recipes.
```

Preference form fields:

- Cooking goal: quick, healthy, high protein, budget, comfort food
- Allergies
- Diet style
- Max cooking time
- Number of meals
- Available tools
- Height and weight, optional

## Pydantic Schemas

Create strict schemas for all agent inputs and outputs.

Suggested schemas:

- `Ingredient`
- `IngredientExtractionResponse`
- `UserPreferences`
- `RecipeCandidate`
- `NutritionEstimate`
- `RecipeSafetyReview`
- `FinalRecipe`
- `AgentWorkflowState`

All LLM outputs must be parsed and validated.

Never trust raw LLM output directly.

## Gemma Client Rules

Create one centralized Gemma client wrapper in:

```text
src/services/gemma_client.py
```

The client should:

- Read API keys from environment variables
- Support image + text calls where needed
- Support text-only calls where needed
- Return raw response text
- Include basic error handling
- Be easy to mock in tests

Do not scatter direct API calls across agent files.

## Prompt Rules

Store prompts in `src/prompts/`.

Each agent should have its own prompt file.

Prompt requirements:

- Ask for structured JSON where needed
- Specify the exact output schema
- Tell the model not to invent unseen ingredients
- Tell the model to mark uncertainty
- Tell the model to respect allergies
- Tell the model to keep nutrition estimates approximate

## Safety Rules

This app is not a medical tool.

Do not claim exact nutrition accuracy.

Do not provide medical, clinical, or weight-loss guarantees.

Always respect allergies.

If a recipe may contain a hidden allergen, warn the user.

If the user provides dangerous or unrealistic constraints, give a safe fallback.

## Coding Rules

- Use clear Python type hints.
- Keep functions small.
- Prefer readable code over clever abstractions.
- Avoid unnecessary dependencies.
- Add docstrings to public functions.
- Do not hard-code API keys.
- Use `.env.example` for required environment variables.
- Keep mock mode available so the app can run without paid API calls.
- Make error messages understandable for a demo user.

## Testing Requirements

Add tests for:

- Pydantic schema validation
- Allergy safety filtering
- JSON parsing
- Orchestrator flow with mocked agents
- At least one sample image workflow, if practical

Run tests with:

```bash
pytest
```

## Local Run Commands

Recommended setup:

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

For macOS/Linux:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Environment Variables

Create `.env.example` with:

```env
GEMMA_API_KEY=your_api_key_here
GEMMA_MODEL_NAME=gemma-4-26b-a4b
APP_MODE=mock
```

Use `APP_MODE=mock` for demos without real model calls.

Use `APP_MODE=live` for real Gemma calls.

## README Requirements

The README must explain:

- What the app does
- Why Gemma 4 is used
- Why the app is multi-agent
- How to install dependencies
- How to run locally
- How to use mock mode
- How to use live model mode
- Example screenshots
- Known limitations
- Future improvements

README should include this architecture summary:

```text
FridgeAgent is not one big recipe prompt. It is a multi-agent workflow where each Gemma-powered agent handles one part of the cooking decision process: image understanding, ingredient verification, user preference normalization, recipe planning, nutrition ranking, allergy safety, and final recipe writing.
```

## Submission Post Requirements

The DEV submission post should include:

1. Problem statement
2. Demo GIF or screenshots
3. Why Gemma 4
4. Model choice
5. Multi-agent architecture
6. Technical implementation
7. What was difficult
8. What was learned
9. Limitations
10. Future improvements
11. GitHub repo link

Suggested opening:

```text
I built FridgeAgent because the hardest part of cooking is often not finding a recipe. It is deciding what to make from what you already have.
```

Suggested model explanation:

```text
Gemma 4 fits this project because the task is naturally multimodal and constraint-heavy. The system needs to understand a fridge image, turn visible food into structured ingredients, reason over allergies and cooking goals, and produce practical recipes with minimal missing items.
```

## Evaluation Checklist

Before submitting, confirm:

- The app runs from a fresh clone
- Mock mode works without API keys
- Live mode is documented
- The multi-agent flow is visible in code
- At least one sample image is included
- README has screenshots
- The app does not hallucinate certainty for unclear ingredients
- Allergy safety is implemented
- The final recipe output is readable
- The DEV post explains why the model was chosen

## Definition of Done

The project is done when:

- `streamlit run app.py` launches the app
- User can upload an image
- App can show detected ingredients
- User can enter preferences
- App can generate recipe cards
- Multi-agent files exist and are used
- Schemas validate agent outputs
- Tests pass
- README explains setup and architecture
- Submission post draft is ready
- Each required change was committed on its own once verified (see "Commit
  Discipline" in AGENTS.md), so the git log is a real, dated track of the work

## Codex Task Prompts

Use these prompts with Codex one by one.

### Task 1: Create project skeleton

```text
Create the project skeleton for FridgeAgent according to CODEX.md.
Use Python, Streamlit, Pydantic, and pytest.
Do not implement real Gemma calls yet.
Add mocked agent outputs so the app can run end-to-end.
```

### Task 2: Add schemas

```text
Implement Pydantic schemas for ingredients, user preferences, recipe candidates, nutrition estimates, safety reviews, final recipes, and agent workflow state.
Add tests for valid and invalid examples.
```

### Task 3: Add multi-agent files

```text
Create separate agent modules for the seven-agent workflow.
Each agent should have a run() function.
Use mocked outputs first.
Wire them through src/orchestrator.py.
Add a test proving the orchestrator calls the workflow end-to-end.
```

### Task 4: Build Streamlit UI

```text
Build app.py as a Streamlit interface.
It should allow image upload, ingredient review, preference input, and recipe generation.
Display final recipe cards clearly.
Add an optional debug expander showing intermediate agent outputs.
```

### Task 5: Implement Gemma client

```text
Implement src/services/gemma_client.py.
Read environment variables from .env.
Support mock mode and live mode.
Keep direct API calls only inside this service.
Make it easy to replace the provider later.
```

### Task 6: Add prompts

```text
Create prompt files for each agent in src/prompts/.
Each prompt should request structured JSON and follow the safety rules in CODEX.md.
Do not invent unseen ingredients.
Respect allergies.
Mark nutrition as approximate.
```

### Task 7: Improve safety

```text
Improve the Allergy Safety Agent.
It should remove recipes containing declared allergens and add warnings for possible hidden allergens.
Add tests for peanut, dairy, gluten, and egg allergies.
```

### Task 8: Prepare challenge submission

```text
Review the repo for challenge-readiness.
Improve README.
Add a demo script.
Add sample outputs.
Check that the project clearly explains the Gemma 4 model choice and multi-agent workflow.
```

## Important Constraints

Do not overbuild.

Do not add user accounts.

Do not add payment logic.

Do not add a complex database unless needed.

Do not fine-tune a model for the MVP.

Do not build a React frontend unless the Streamlit MVP is complete.

Do not make exact health or nutrition claims.

Do not hide uncertainty from the user.

## Priority Order

If time is limited, prioritize in this order:

1. Working Streamlit demo
2. Clear multi-agent architecture
3. Gemma 4 image and text usage
4. Allergy safety
5. Good README
6. Good DEV post
7. Tests
8. UI polish
9. Optional persistence
10. Optional deployment

## Final Product Vision

FridgeAgent should feel like this:

```text
I opened my fridge, took a photo, answered a few questions, and got realistic meals I can cook today without buying many extra ingredients.
```

The technical story should feel like this:

```text
Gemma 4 powers a multimodal multi-agent workflow that turns messy real-world food images and personal constraints into safe, useful recipe plans.
```
