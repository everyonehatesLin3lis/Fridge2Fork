from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class HermesTraceEntry(BaseModel):
    """One deterministic handoff recorded by Hermes."""

    step_name: str
    agent_name: str
    action: str
    handoff_payload: dict[str, Any] = Field(default_factory=dict)
    decision_note: str


class HermesOrchestrator:
    """Strict message-passing layer for the FridgeAgent workflow.

    Hermes is intentionally deterministic. It does not identify ingredients,
    rank recipes, check allergies, or write recipes. It only enforces the
    allowed agent order, prevents repeated agent calls, and records clean
    handoffs for debugging.
    """

    allowed_order: tuple[str, ...] = (
        "vision",
        "constraints",
        "recipe_planner",
        "final_recipe",
    )

    display_names: dict[str, str] = {
        "vision": "Vision Stage",
        "constraints": "Constraint Stage",
        "recipe_planner": "Recipe Planner Stage",
        "final_recipe": "Final Recipe Stage",
    }

    def __init__(self, max_steps: int | None = None) -> None:
        self.max_steps = max_steps or len(self.allowed_order)
        self.steps_run: list[str] = []
        self.trace: list[HermesTraceEntry] = []

    def prepare_handoff(
        self,
        step_name: str,
        handoff_payload: dict[str, Any] | None = None,
        decision_note: str | None = None,
    ) -> HermesTraceEntry:
        """Validate and record the next specialist-agent handoff."""
        self._validate_next_step(step_name)
        self.steps_run.append(step_name)

        entry = HermesTraceEntry(
            step_name=step_name,
            agent_name=self.display_names.get(step_name, step_name),
            action="call_agent",
            handoff_payload=handoff_payload or {},
            decision_note=decision_note or f"Calling {step_name} in the fixed workflow order.",
        )
        self.trace.append(entry)
        return entry

    def _validate_next_step(self, step_name: str) -> None:
        if len(self.steps_run) >= self.max_steps:
            raise RuntimeError("Hermes stopped the flow: max agent steps reached.")

        if step_name in self.steps_run:
            raise RuntimeError(f"Hermes stopped the flow: {step_name} already ran.")

        if not self.steps_run and step_name == "constraints":
            return

        if not self.steps_run:
            expected_next = self.allowed_order[0]
        else:
            previous_index = self.allowed_order.index(self.steps_run[-1])
            expected_next = self.allowed_order[previous_index + 1]
        if step_name != expected_next:
            raise RuntimeError(
                "Hermes stopped the flow: invalid agent order. "
                f"Expected {expected_next}, got {step_name}."
            )

    def trace_dump(self) -> list[dict[str, Any]]:
        """Return a serializable trace for Streamlit debug output and tests."""
        return [entry.model_dump() for entry in self.trace]
