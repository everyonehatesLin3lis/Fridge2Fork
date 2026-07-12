"""Summarize FridgeAgent LLM telemetry: vision detection quality and RAG retrieval performance.

Usage:
    python scripts/llm_ops_report.py            # print a summary of collected telemetry
    python scripts/llm_ops_report.py --check    # exit non-zero when performance budgets are violated

Telemetry is collected automatically while the app runs:
- data/telemetry/vision_detection.jsonl  (one row per analyzed image)
- data/telemetry/rag_retrieval.jsonl     (one row per recipe reference search)
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.services.telemetry import read_events, telemetry_dir


# Performance budgets for --check mode.
RAG_P95_LATENCY_BUDGET_MS = 3000.0
VISION_PARSE_SUCCESS_BUDGET = 0.5  # at least half of vision calls must yield parseable JSON


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round(fraction * (len(ordered) - 1))))
    return ordered[index]


def vision_summary() -> dict | None:
    events = read_events("vision_detection")
    if not events:
        return None
    latencies = [event["latency_ms"] for event in events if isinstance(event.get("latency_ms"), (int, float))]
    parse_ok = [bool(event.get("parse_ok")) for event in events]
    confidences = [event["confidence_mean"] for event in events if isinstance(event.get("confidence_mean"), (int, float))]
    ingredient_counts = [event.get("ingredient_count", 0) for event in events]
    low_confidence = [event.get("low_confidence_count", 0) for event in events]
    errors: dict[str, int] = {}
    for event in events:
        if event.get("error_type"):
            errors[event["error_type"]] = errors.get(event["error_type"], 0) + 1
    return {
        "calls": len(events),
        "parse_success_rate": round(sum(parse_ok) / len(parse_ok), 3),
        "latency_mean_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "latency_p95_ms": round(_percentile(latencies, 0.95), 1) if latencies else None,
        "avg_ingredients_per_image": round(statistics.mean(ingredient_counts), 2) if ingredient_counts else None,
        "avg_confidence": round(statistics.mean(confidences), 3) if confidences else None,
        "avg_low_confidence_items": round(statistics.mean(low_confidence), 2) if low_confidence else None,
        "errors": errors,
    }


def rag_summary() -> dict | None:
    events = read_events("rag_retrieval")
    if not events:
        return None
    latencies = [event["latency_ms"] for event in events if isinstance(event.get("latency_ms"), (int, float))]
    hits = [event.get("result_count", 0) > 0 for event in events]
    top_scores = [event["top_score"] for event in events if isinstance(event.get("top_score"), (int, float))]
    return {
        "searches": len(events),
        "hit_rate": round(sum(hits) / len(hits), 3),
        "latency_mean_ms": round(statistics.mean(latencies), 1) if latencies else None,
        "latency_p95_ms": round(_percentile(latencies, 0.95), 1) if latencies else None,
        "avg_top_score": round(statistics.mean(top_scores), 1) if top_scores else None,
    }


def print_section(title: str, summary: dict | None) -> None:
    print(f"\n== {title} ==")
    if summary is None:
        print("no telemetry collected yet")
        return
    for key, value in summary.items():
        print(f"{key}: {value}")


def check_budgets(vision: dict | None, rag: dict | None) -> list[str]:
    violations = []
    if rag and rag["latency_p95_ms"] is not None and rag["latency_p95_ms"] > RAG_P95_LATENCY_BUDGET_MS:
        violations.append(
            f"RAG p95 latency {rag['latency_p95_ms']}ms exceeds budget {RAG_P95_LATENCY_BUDGET_MS}ms"
        )
    if vision and vision["parse_success_rate"] < VISION_PARSE_SUCCESS_BUDGET:
        violations.append(
            f"Vision parse success rate {vision['parse_success_rate']} below budget {VISION_PARSE_SUCCESS_BUDGET}"
        )
    return violations


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail when performance budgets are violated")
    args = parser.parse_args()

    print(f"Telemetry directory: {telemetry_dir()}")
    vision = vision_summary()
    rag = rag_summary()
    print_section("Vision model detection", vision)
    print_section("Recipe RAG retrieval", rag)

    if args.check:
        violations = check_budgets(vision, rag)
        if violations:
            print("\nBudget violations:")
            for violation in violations:
                print(f"- {violation}")
            return 1
        print("\nAll performance budgets satisfied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
