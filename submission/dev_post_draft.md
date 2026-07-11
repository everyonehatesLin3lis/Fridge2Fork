# Weekend Challenge: Passion Edition Submission Draft

Tags: #weekendchallenge

## What I built

FridgeAgent already does something I care about: it turns whatever is actually sitting
in your fridge into a real, cookable recipe instead of another generic AI recipe. For
Passion Edition, I added **Passion Mode** on top of that base.

You can now tell FridgeAgent what you're passionate about cooking right now: a rivalry
dish, a family recipe you're trying to nail, or a match-day snack for when your team
plays. That note flows through the full four-agent workflow and comes back as a short,
personal line on every recipe card tying the dish back to what you said you cared about.

With the World Cup going on, I kept picturing someone standing in front of an open
fridge an hour before kickoff, half-watching the pre-game show, trying to figure out
what to cook with three ingredients and a lot of nervous energy. Passion Mode is built
for that moment.

## What's new for this challenge

- A "What are you passionate about cooking right now?" input in the Streamlit UI.
- `passion_note` added to the validated user preference schema.
- The Recipe Planner Agent uses the note as theming context for both the deterministic
  planner and the local/live LLM prompt, and a `passion_line` field is guaranteed on
  every recipe (deterministic backstop even if the LLM omits it).
- The Final Recipe Agent carries `passion_line` through to the user-facing card.
- **Best Use of Google AI**: `GemmaClient` gained a real `APP_MODE=google` provider
  using the current `google-genai` SDK against the Gemini API, alongside the existing
  mock and local Ollama modes.
- New tests for schema validation, the passion pipeline, and the Google AI client's
  success and failure paths.

## Disclosure

The base project (fridge photo upload, four-agent workflow, recipe RAG, Hermes
orchestration) predates this challenge and was originally built for a separate
challenge submission. Everything listed above under "What's new for this challenge"
was designed and built within the July 10-13, 2026 challenge window on top of that
existing base, per the "riffing on prior work" allowance in the challenge FAQ.

## Demo

See `submission/demo_script.md` for the walkthrough: type a passion note, generate
recipes, and see the personal line on each card.

Repo link: https://github.com/everyonehatesLin3lis/Fridge2Fork
