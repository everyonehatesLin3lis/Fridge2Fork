# Demo Script

1. Launch the app with `streamlit run app.py`.
2. For real image detection, launch local mode with `streamlit run main.py` and `APP_MODE=local`.
3. Upload up to five fridge or food photos.
4. Review detected ingredients and edit any uncertain items.
5. In "What are you passionate about cooking right now?", type something like
   *"my grandmother's garlic soup"* or *"a match-day snack for when my team plays"*.
6. Select a cooking goal, allergies, diet style, time limit, portions, tools, gender, height, and weight.
7. Generate recipes.
8. Point out the italic passion line under each recipe title, tying the dish back to the
   note from step 5.
9. Open the debug expander to show the four-agent workflow outputs, including the
   Recipe Planner Agent's passion theming context.
10. Open the Hermes Agent audit expander and run the audit.
11. Show that Hermes Agent checks cooking feasibility, portion math, allergy risk, and missing binder/base issues.
12. Optional (Best Use of Google AI): set `APP_MODE=google` and `GOOGLE_API_KEY`, then rerun
    to show recipe generation and the local chat assistant running on the real Gemini API.
