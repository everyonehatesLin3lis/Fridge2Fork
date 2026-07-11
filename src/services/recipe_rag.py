from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_INDEX_PATH = Path("data/recipe_rag_index.jsonl")


@dataclass(frozen=True)
class RecipeReference:
    title: str
    ingredients: list[str]
    directions: list[str]
    source: str
    score: float = 0.0

    def to_prompt_block(self) -> str:
        ingredient_text = ", ".join(self.ingredients[:12])
        direction_text = " ".join(self.directions[:5])
        return (
            f"Title: {self.title}\n"
            f"Ingredients: {ingredient_text}\n"
            f"Cooking pattern: {direction_text}\n"
            f"Source: {self.source}"
        )


class RecipeRagStore:
    """Tiny local lexical RAG store over a sampled recipe dataset index."""

    def __init__(self, index_path: Path | str = DEFAULT_INDEX_PATH) -> None:
        self.index_path = Path(index_path)
        self._records: list[RecipeReference] | None = None

    def is_ready(self) -> bool:
        return self.index_path.exists() and self.index_path.stat().st_size > 0

    def search(
        self,
        ingredients: list[str],
        goal: str = "",
        tools: list[str] | None = None,
        limit: int = 3,
    ) -> list[RecipeReference]:
        """Return the most relevant recipe references for confirmed ingredients."""
        if not self.is_ready():
            return []
        if not ingredients:
            return []

        query_terms = _tokens(" ".join([*ingredients, goal, *(tools or [])]))
        if not query_terms:
            return []

        scored = []
        for record in self._load_records():
            searchable = _tokens(
                " ".join(
                    [
                        record.title,
                        " ".join(record.ingredients),
                        " ".join(record.directions[:8]),
                    ]
                )
            )
            overlap = query_terms & searchable
            if not overlap:
                continue
            ingredient_hits = sum(
                1
                for ingredient in ingredients
                if _tokens(ingredient) and _tokens(ingredient).issubset(searchable)
            )
            score = len(overlap) + ingredient_hits * 3
            scored.append(
                RecipeReference(
                    title=record.title,
                    ingredients=record.ingredients,
                    directions=record.directions,
                    source=record.source,
                    score=float(score),
                )
            )

        return sorted(scored, key=lambda item: item.score, reverse=True)[:limit]

    def _load_records(self) -> list[RecipeReference]:
        if self._records is not None:
            return self._records

        records = []
        with self.index_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                records.append(
                    RecipeReference(
                        title=str(payload.get("title", "Untitled recipe")),
                        ingredients=_as_list(payload.get("ingredients")),
                        directions=_as_list(payload.get("directions")),
                        source=str(payload.get("source", "kaggle recipe dataset")),
                    )
                )
        self._records = records
        return records


def format_references_for_prompt(references: list[RecipeReference]) -> str:
    """Format retrieved recipes as compact grounding context for Gemma."""
    if not references:
        return "No local recipe references were retrieved. Use general cooking knowledge and be explicit."
    return "\n\n".join(
        f"Reference {index} (score {reference.score:.0f})\n{reference.to_prompt_block()}"
        for index, reference in enumerate(references, start=1)
    )


def _tokens(text: str) -> set[str]:
    return {token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9_]+", text.lower()) if len(token) > 2}


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            parsed = json.loads(stripped)
            if isinstance(parsed, list):
                return [str(item).strip() for item in parsed if str(item).strip()]
        except json.JSONDecodeError:
            pass
        parts = re.split(r"\r?\n| \| |;", stripped)
        return [part.strip(" -") for part in parts if part.strip(" -")]
    return [str(value)]
