from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.services.hermes_agent_audit import run_hermes_agent_audit


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit a Fridge2Fork workflow JSON with Hermes Agent.")
    parser.add_argument("--input", required=True, help="Path to workflow JSON, such as data/sample_outputs/eight_ingredient_debug.json")
    parser.add_argument("--output", default="data/sample_outputs/hermes_agent_audit.json")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)
    workflow_text = input_path.read_text(encoding="utf-8")
    audit = run_hermes_agent_audit(workflow_text, timeout_seconds=args.timeout)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(json.dumps(audit, indent=2))
    print(f"Wrote Hermes Agent audit to {output_path}")


if __name__ == "__main__":
    main()
