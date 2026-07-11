from __future__ import annotations

import pytest

from src.orchestration import HermesOrchestrator


def test_hermes_records_handoff_trace() -> None:
    hermes = HermesOrchestrator()

    entry = hermes.prepare_handoff(
        "vision",
        {"input": "uploaded image"},
        "Vision runs once at the start.",
    )

    assert entry.action == "call_agent"
    assert hermes.steps_run == ["vision"]
    assert hermes.trace_dump()[0]["agent_name"] == "Vision Stage"


def test_hermes_blocks_repeated_agent_call() -> None:
    hermes = HermesOrchestrator()
    hermes.prepare_handoff("vision")

    with pytest.raises(RuntimeError, match="already ran"):
        hermes.prepare_handoff("vision")


def test_hermes_blocks_out_of_order_agent_call() -> None:
    hermes = HermesOrchestrator()

    with pytest.raises(RuntimeError, match="invalid agent order"):
        hermes.prepare_handoff("recipe_planner")


def test_hermes_blocks_max_steps() -> None:
    hermes = HermesOrchestrator(max_steps=1)
    hermes.prepare_handoff("vision")

    with pytest.raises(RuntimeError, match="max agent steps"):
        hermes.prepare_handoff("constraints")
