"""RAG retrieval correctness and performance checks.

These tests run against a small committed fixture index so they work in CI
without the full Kaggle-derived index. When the real local index is present,
an extra test verifies retrieval performance against it too.
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from src.services.recipe_rag import DEFAULT_INDEX_PATH, RecipeRagStore, format_references_for_prompt


FIXTURE_INDEX = Path(__file__).parent / "fixtures" / "rag_index_fixture.jsonl"

# Performance budgets. The fixture search is tiny; the real index budget is
# deliberately generous because it scans a ~25k-record JSONL sample.
FIXTURE_SEARCH_BUDGET_SECONDS = 2.0
REAL_INDEX_SEARCH_BUDGET_SECONDS = 10.0


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEMETRY_DIR", str(tmp_path / "telemetry"))
    return RecipeRagStore(index_path=FIXTURE_INDEX)


def test_fixture_index_is_ready(store):
    assert store.is_ready()


def test_search_returns_relevant_recipes(store):
    results = store.search(ingredients=["chicken", "rice"], goal="quick")
    assert results, "expected at least one retrieval hit for chicken + rice"
    top = results[0]
    searchable = (top.title + " " + " ".join(top.ingredients)).lower()
    assert "chicken" in searchable or "rice" in searchable


def test_search_ranks_ingredient_matches_higher(store):
    results = store.search(ingredients=["chicken", "rice", "onion"], limit=5)
    assert results[0].title == "Quick Chicken and Rice Skillet"
    scores = [reference.score for reference in results]
    assert scores == sorted(scores, reverse=True)


def test_search_with_no_ingredients_returns_empty(store):
    assert store.search(ingredients=[]) == []


def test_search_missing_index_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEMETRY_DIR", str(tmp_path / "telemetry"))
    missing = RecipeRagStore(index_path=tmp_path / "missing.jsonl")
    assert not missing.is_ready()
    assert missing.search(ingredients=["chicken"]) == []


def test_search_latency_within_budget(store):
    store.search(ingredients=["warmup"])  # load records outside the timed run
    start = time.perf_counter()
    store.search(ingredients=["chicken", "rice", "onion"], goal="quick", tools=["pan"])
    elapsed = time.perf_counter() - start
    assert elapsed < FIXTURE_SEARCH_BUDGET_SECONDS, f"fixture retrieval took {elapsed:.2f}s"


def test_search_logs_retrieval_telemetry(store, tmp_path):
    from src.services import telemetry

    store.search(ingredients=["chicken", "rice"], goal="quick")
    events = telemetry.read_events("rag_retrieval")
    assert events, "expected a rag_retrieval telemetry event"
    event = events[-1]
    assert event["result_count"] >= 1
    assert event["latency_ms"] >= 0
    assert event["query_ingredients"] == ["chicken", "rice"]


def test_format_references_for_prompt(store):
    results = store.search(ingredients=["chicken", "rice"])
    prompt_block = format_references_for_prompt(results)
    assert "Title:" in prompt_block
    assert "Reference 1" in prompt_block


@pytest.mark.skipif(not DEFAULT_INDEX_PATH.exists(), reason="full local RAG index not present")
def test_real_index_retrieval_and_latency(tmp_path, monkeypatch):
    monkeypatch.setenv("TELEMETRY_DIR", str(tmp_path / "telemetry"))
    real_store = RecipeRagStore()
    real_store.search(ingredients=["warmup"])  # load the index outside the timed run
    start = time.perf_counter()
    results = real_store.search(ingredients=["chicken", "rice", "onion"], goal="quick")
    elapsed = time.perf_counter() - start
    assert results, "expected hits from the real index for common ingredients"
    assert elapsed < REAL_INDEX_SEARCH_BUDGET_SECONDS, f"real index retrieval took {elapsed:.2f}s"
