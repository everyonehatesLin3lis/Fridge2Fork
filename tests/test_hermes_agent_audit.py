from __future__ import annotations

import json

from src.services.hermes_agent_audit import build_hermes_audit_prompt, run_hermes_agent_audit


def test_hermes_audit_prompt_contains_context_and_workflow() -> None:
    prompt = build_hermes_audit_prompt('{"final_recipes": []}')

    assert "Fridge2Fork Hermes Agent Context" in prompt
    assert "Cooking Feasibility Rules" in prompt
    assert '"final_recipes": []' in prompt


def test_hermes_audit_returns_fallback_when_cli_missing(monkeypatch) -> None:
    monkeypatch.setattr("src.services.hermes_agent_audit.shutil.which", lambda command: None)

    audit = run_hermes_agent_audit({"final_recipes": []})

    assert audit["used_hermes_agent"] is False
    assert audit["status"] == "unavailable"
    assert audit["local_fallback_audit"]["issues"]


def test_hermes_fallback_flags_missing_amounts(monkeypatch) -> None:
    monkeypatch.setattr("src.services.hermes_agent_audit.shutil.which", lambda command: None)
    payload = {
        "final_recipes": [
            {
                "title": "Egg Bowl",
                "ingredients_used": ["eggs"],
                "ingredient_amounts": [],
                "steps": ["Cook eggs."],
            }
        ]
    }

    audit = run_hermes_agent_audit(json.dumps(payload))

    issues = audit["local_fallback_audit"]["issues"]
    assert any("Missing amount rows" in issue["issue"] for issue in issues)
