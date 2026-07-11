# AGENTS.md

Read CODEX.md before making changes.

Follow the project scope, architecture, coding rules, and definition of done in CODEX.md.
Keep the application MVP-focused and do not add unnecessary features.

Current agent architecture uses exactly 4 specialist agents:

1. `vision_agent`: image ingredient detection, normalization, uncertainty, and verification.
2. `constraints_agent`: user preferences, portions, allergies, time, goals, and tools.
3. `recipe_planner_agent`: recipe RAG retrieval, planning, portion math, cooking detail, and rough nutrition ranking.
4. `final_recipe_agent`: allergy safety filtering, warnings, and final recipe card writing.

Hermes is the orchestrator, not a fifth agent. If older CODEX.md examples mention a seven-agent workflow, treat the 4-agent architecture above as the current source of truth.

## Commit Discipline

Commit to git as soon as each required change is complete and verified (tests pass,
app runs), rather than batching many unrelated changes into one commit. Use a short,
descriptive message per commit (schema change, agent change, UI change, docs change,
etc).

This keeps a real, timestamped track record of work done during any active challenge
window (see the DEV Weekend Challenge: Passion Edition section in README.md), which
several DEV Challenge rules require to prove a project was actually built within the
submission window and was not an old project reused as-is.
