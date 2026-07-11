# Hermes Agent Challenge Submission Draft

I built Fridge2Fork because recipe generation often fails at the most human part
of cooking: knowing whether the dish can actually be made from what is in front
of you.

Fridge2Fork is a local fridge-to-recipe assistant. A user can upload up to five
fridge or food photos, or type confirmed ingredients manually. The app verifies
ingredients, applies constraints like allergies and cooking time, searches a
local Kaggle recipe RAG index, calculates portions, and produces practical
recipe cards with measurable ingredient amounts and concrete cooking steps.

The app has four specialist agents:

1. Vision Agent: detects and merges ingredients from up to five photos.
2. Constraints Agent: normalizes goals, allergies, portions, time, tools, and nutrition context.
3. Recipe Planner Agent: retrieves recipe references, calculates portions, validates feasibility, and ranks rough nutrition.
4. Final Recipe Agent: filters unsafe recipes and writes final cards.

Hermes appears in two layers:

- `HermesOrchestrator` is the deterministic in-app messenger. It prevents loops
  and keeps the workflow bounded.
- The real Nous Research Hermes Agent is used as an external audit layer. The app
  can call `hermes chat -Q -q` with the generated workflow JSON and project
  context files so Hermes Agent can critique feasibility, portions, allergy
  safety, missing binders/bases, and bad cooking steps.

The most important lesson was that recipe generation needs a critic. Without a
validator, an AI can produce things like “cut yogurt into pieces” or “make a pie”
without a binder or base. The Hermes Agent audit step gives the project an
agentic review pass that asks: can this actually be cooked?

What is original here:

- multi-photo ingredient detection and merge
- Hermes-controlled four-agent workflow
- Kaggle recipe dataset transformed into local RAG
- deterministic feasibility checker inside planning
- external Hermes Agent audit for final workflow review
- portion-aware recipe cards with grams, counts, and nutrition context

Limitations:

- nutrition is approximate, not medical advice
- local image quality depends on the configured model
- Hermes Agent audit requires the external `hermes` CLI to be installed and configured
- RAG uses a compact local index sample for speed

Repo link: TODO
