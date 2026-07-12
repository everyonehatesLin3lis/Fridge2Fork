from __future__ import annotations

from pathlib import Path


WEB_HTML = Path(__file__).resolve().parents[1] / "web" / "index.html"


def test_primary_experience_focuses_on_decision_time_and_calories_per_portion() -> None:
    html = WEB_HTML.read_text(encoding="utf-8")

    assert "Less thinking." in html
    assert "saving you time" in html
    assert "kcal / portion" in html
