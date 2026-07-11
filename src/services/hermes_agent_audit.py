from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


HERMES_CONTEXT_FILES = [
    Path("hermes/fridge2fork_context.md"),
    Path("hermes/cooking_feasibility_rules.md"),
    Path("hermes/recipe_audit_task.md"),
]


def run_hermes_agent_audit(workflow_output: dict[str, Any] | str, timeout_seconds: int = 180) -> dict[str, Any]:
    """Run a Hermes Agent audit if the CLI is installed, otherwise return a local fallback audit."""
    workflow_json = workflow_output if isinstance(workflow_output, str) else json.dumps(workflow_output, indent=2)
    prompt = build_hermes_audit_prompt(workflow_json)
    hermes_path = shutil.which("hermes")

    if hermes_path is None:
        return {
            "status": "unavailable",
            "used_hermes_agent": False,
            "summary": "Hermes Agent CLI was not found on PATH.",
            "issues": [
                {
                    "severity": "medium",
                    "recipe": "workflow",
                    "issue": "The external Hermes Agent audit could not run because the `hermes` command is not installed or configured.",
                    "fix": "Install Hermes Agent, run `hermes setup`, then retry the audit.",
                }
            ],
            "recommended_changes": [
                "Install Hermes Agent from the official Nous Research quickstart.",
                "Run `hermes chat -Q -q \"hello\"` once in the terminal to confirm setup.",
            ],
            "local_fallback_audit": _local_fallback_audit(workflow_json),
            "command": "hermes chat -Q -q <audit prompt>",
        }

    command = [hermes_path, "chat", "-Q", "-q", prompt]
    try:
        completed = subprocess.run(
            command,
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "used_hermes_agent": True,
            "summary": "Hermes Agent audit timed out.",
            "issues": [
                {
                    "severity": "medium",
                    "recipe": "workflow",
                    "issue": "Hermes Agent did not finish within the timeout.",
                    "fix": "Retry with a shorter workflow JSON or increase the timeout.",
                }
            ],
            "recommended_changes": ["Retry the audit after confirming Hermes Agent provider latency."],
            "command": " ".join(command[:3]) + " <audit prompt>",
        }

    parsed = _parse_json_object(completed.stdout)
    if parsed:
        parsed.setdefault("used_hermes_agent", True)
        parsed.setdefault("status", "warning" if completed.returncode else "pass")
        parsed.setdefault("raw_stdout", completed.stdout)
        parsed.setdefault("raw_stderr", completed.stderr)
        parsed.setdefault("command", " ".join(command[:3]) + " <audit prompt>")
        return parsed

    return {
        "status": "warning" if completed.returncode == 0 else "fail",
        "used_hermes_agent": True,
        "summary": "Hermes Agent ran, but did not return parseable JSON.",
        "issues": [
            {
                "severity": "medium",
                "recipe": "workflow",
                "issue": "Audit response was not valid JSON.",
                "fix": "Use the raw Hermes Agent output below or rerun the audit.",
            }
        ],
        "recommended_changes": ["Rerun Hermes Agent audit with stricter JSON instructions if needed."],
        "raw_stdout": completed.stdout,
        "raw_stderr": completed.stderr,
        "returncode": completed.returncode,
        "command": " ".join(command[:3]) + " <audit prompt>",
    }


def build_hermes_audit_prompt(workflow_json: str) -> str:
    context = "\n\n".join(_read_context_file(path) for path in HERMES_CONTEXT_FILES)
    return f"""
{context}

Audit this Fridge2Fork workflow output. Use your tool/reasoning abilities as Hermes Agent to inspect the JSON and return only the requested JSON audit object.

Workflow output:
```json
{workflow_json}
```
""".strip()


def _read_context_file(path: Path) -> str:
    if not path.exists():
        return f"# Missing context file: {path}"
    return path.read_text(encoding="utf-8")


def _parse_json_object(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        parsed = json.loads(stripped)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(stripped[start : end + 1])
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _local_fallback_audit(workflow_json: str) -> dict[str, Any]:
    try:
        payload = json.loads(workflow_json)
    except json.JSONDecodeError:
        return {
            "status": "warning",
            "summary": "Local fallback could not parse workflow JSON.",
            "issues": [],
            "recommended_changes": ["Check workflow JSON serialization."],
        }

    issues = []
    final_recipes = _extract_final_recipes(payload)
    if not final_recipes:
        issues.append(
            {
                "severity": "high",
                "recipe": "workflow",
                "issue": "No final recipes were produced.",
                "fix": "Confirm ingredients or run image detection in local mode before planning.",
            }
        )

    for recipe in final_recipes:
        title = recipe.get("title", "recipe")
        ingredients = recipe.get("ingredients_used", [])
        amount_names = {amount.get("name") for amount in recipe.get("ingredient_amounts", [])}
        missing_amounts = [ingredient for ingredient in ingredients if ingredient not in amount_names]
        if missing_amounts:
            issues.append(
                {
                    "severity": "high",
                    "recipe": title,
                    "issue": f"Missing amount rows for: {', '.join(missing_amounts)}.",
                    "fix": "Add per-portion and total amount rows for every used ingredient.",
                }
            )
        steps_text = " ".join(recipe.get("steps", [])).lower()
        if any(term in steps_text for term in ["cut yogurt", "slice yogurt", "cut cottage cheese"]):
            issues.append(
                {
                    "severity": "high",
                    "recipe": title,
                    "issue": "Soft dairy is described as cuttable.",
                    "fix": "Rewrite as a bowl, spread, sauce, or topping instead of cutting soft dairy.",
                }
            )

    return {
        "status": "fail" if any(issue["severity"] == "high" for issue in issues) else "pass",
        "summary": "Local fallback audit completed without Hermes Agent.",
        "issues": issues,
        "recommended_changes": [
            "Use Hermes Agent CLI for the official agentic audit layer.",
            "Keep the deterministic fallback as a safety net inside the app.",
        ],
    }


def _extract_final_recipes(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(payload.get("final_recipes"), list):
        return payload["final_recipes"]

    recipes: list[dict[str, Any]] = []
    for run in payload.get("runs", []):
        result = run.get("result", {}) if isinstance(run, dict) else {}
        for recipe in result.get("final_recipes", []):
            if isinstance(recipe, dict):
                recipes.append(recipe)
    return recipes
