# Fridge2Fork Hermes Agent Context

Fridge2Fork is a local fridge-to-recipe assistant. The app accepts typed ingredients
or up to five fridge/food photos, verifies available ingredients, applies user
constraints, searches a local Kaggle recipe RAG index, plans recipes, estimates
rough nutrition, and writes recipe cards.

Hermes Agent is used as an external agentic audit layer. It reviews generated
workflow JSON and checks whether the recipe plan is physically cookable,
safe, portion-aware, and aligned with the user's constraints.

Important project rules:

- Do not invent ingredients that were not verified or explicitly listed as pantry basics.
- Treat nutrition as approximate and not medical advice.
- Be conservative with allergies.
- Verify that every used ingredient has a per-portion and total amount.
- Verify that cooking steps make physical sense for the ingredient roles.
- Wet or soft dairy should not be described as cuttable pieces or seared at high heat.
- Dish names such as pie, wrap, bake, omelette, casserole, and skillet need a compatible base, binder, or cooking structure.
- If a recipe is invalid, suggest the simplest valid conversion.
