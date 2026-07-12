"""Telemetry collection checks: vision confidence tracking and the ops report."""

from __future__ import annotations

import pytest

from src.schemas.ingredient_schema import Ingredient, IngredientExtractionResponse
from src.services import telemetry


@pytest.fixture(autouse=True)
def isolated_telemetry(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEMETRY_DIR", str(tmp_path / "telemetry"))


def test_log_event_appends_jsonl_rows():
    telemetry.log_event("unit_test", {"value": 1})
    telemetry.log_event("unit_test", {"value": 2})
    events = telemetry.read_events("unit_test")
    assert [event["value"] for event in events] == [1, 2]
    assert all("timestamp" in event for event in events)


def test_read_events_missing_kind_returns_empty():
    assert telemetry.read_events("never_logged") == []


def test_vision_detection_telemetry_records_confidence(monkeypatch):
    from src.agents import vision_agent
    from src.config import get_settings

    detection = IngredientExtractionResponse(
        ingredients=[
            Ingredient(name="eggs", category="protein", confidence=0.9, use_soon=False),
            Ingredient(name="mystery jar", category="other", confidence=0.3, use_soon=False),
        ],
        uncertain_items=["foggy shelf item"],
    )
    vision_agent._log_detection_telemetry(get_settings(), 123.4, "raw", detection, None)

    events = telemetry.read_events("vision_detection")
    assert len(events) == 1
    event = events[0]
    assert event["parse_ok"] is True
    assert event["ingredient_count"] == 2
    assert event["low_confidence_count"] == 1
    assert event["confidence_min"] == 0.3
    assert event["confidence_max"] == 0.9
    assert event["latency_ms"] == 123.4


def test_vision_detection_telemetry_records_failures():
    from src.agents import vision_agent
    from src.config import get_settings

    vision_agent._log_detection_telemetry(
        get_settings(), 120000.0, "", None, RuntimeError("Local Gemma timed out")
    )
    event = telemetry.read_events("vision_detection")[-1]
    assert event["parse_ok"] is False
    assert event["error_type"] == "RuntimeError"
    assert "timed out" in event["error_message"]
    assert event["ingredient_count"] == 0


def test_ops_report_summarizes_and_checks_budgets():
    import importlib

    report = importlib.import_module("scripts.llm_ops_report")

    telemetry.log_event(
        "vision_detection",
        {"latency_ms": 900.0, "parse_ok": True, "ingredient_count": 4, "confidence_mean": 0.8, "low_confidence_count": 0},
    )
    telemetry.log_event(
        "rag_retrieval",
        {"latency_ms": 45.0, "result_count": 3, "top_score": 12.0},
    )

    vision = report.vision_summary()
    rag = report.rag_summary()
    assert vision["calls"] == 1
    assert vision["parse_success_rate"] == 1.0
    assert rag["hit_rate"] == 1.0
    assert report.check_budgets(vision, rag) == []

    telemetry.log_event(
        "rag_retrieval",
        {"latency_ms": 99999.0, "result_count": 0, "top_score": None},
    )
    slow_rag = report.rag_summary()
    assert report.check_budgets(vision, slow_rag), "expected a budget violation for slow retrieval"
