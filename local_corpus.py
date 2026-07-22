"""Read-only access to the versioned corpus snapshot bundled with this repository."""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT = ROOT / "data" / "corpus.json"


def _normalise(value: str) -> str:
    return "".join(str(value).casefold().split())


def _card(row: dict[str, Any]) -> dict[str, Any]:
    """Return only the public lexical material exposed to agents."""
    return {
        "id": row["id"],
        "term": row["term"],
        "explanation": row.get("explanation", ""),
        "examples": list(row.get("examples", [])),
        "derivations": list(row.get("derivations", [])),
        "sources": list(row.get("sources", [])),
        "version": row.get("version", 1),
    }


@dataclass
class LocalCorpus:
    """A snapshot-backed corpus without network or database dependencies."""

    terms: list[dict[str, Any]]
    relations: list[dict[str, Any]]
    exported_at: str

    def __post_init__(self) -> None:
        self.by_id = {row["id"]: row for row in self.terms}
        self.aliases: dict[str, list[str]] = defaultdict(list)
        for row in self.terms:
            term_id = row["id"]
            self.aliases[_normalise(row["term"])].append(term_id)
            for alias in row.get("derivations", []):
                self.aliases[_normalise(alias)].append(term_id)
        self.neighbors: dict[str, list[dict[str, str]]] = defaultdict(list)
        for relation in self.relations:
            source_id = relation.get("source_id")
            target_id = relation.get("target_id")
            if source_id in self.by_id and target_id in self.by_id:
                edge = {"source_id": source_id, "target_id": target_id, "relation": relation.get("relation", "related")}
                self.neighbors[source_id].append(edge)
                self.neighbors[target_id].append(edge)

    @classmethod
    def from_file(cls, path: Path = DEFAULT_SNAPSHOT) -> "LocalCorpus":
        raw = json.loads(path.read_text(encoding="utf-8"))
        if raw.get("format") != "abstract-meme-corpus/v1":
            raise ValueError(f"unsupported corpus snapshot: {path}")
        return cls(
            terms=list(raw.get("terms", [])),
            relations=list(raw.get("relations", [])),
            exported_at=str(raw.get("exported_at", "")),
        )

    def search(self, query: str, limit: int = 64) -> list[dict[str, Any]]:
        """Literal lookup over terms, recorded variants, explanations, and examples.

        This is intentionally not semantic ranking.  A result is returned only
        when the query text occurs in material carried by this snapshot.
        """
        needle = _normalise(query)
        if not needle:
            return []
        selected: list[str] = []

        def add(term_id: str) -> None:
            if term_id not in selected:
                selected.append(term_id)

        # Exact recorded names and variants retain their snapshot order.
        for term_id in self.aliases.get(needle, []):
            add(term_id)

        for row in self.terms:
            material = [row["term"], *row.get("derivations", []), row.get("explanation", ""), *row.get("examples", [])]
            if any(needle in _normalise(piece) for piece in material):
                add(row["id"])
            if len(selected) >= max(1, min(int(limit), 200)):
                break
        return [_card(self.by_id[term_id]) for term_id in selected[: max(1, min(int(limit), 200))]]

    def read(self, term_id: str) -> dict[str, Any] | None:
        row = self.by_id.get(term_id)
        return _card(row) if row else None

    def activate(self, context: str, cues: list[str], limit: int = 24) -> dict[str, Any]:
        """Expose terms reached by the caller's own contextual cues and edges."""
        bounded_limit = max(1, min(int(limit), 80))
        clean_cues = list(dict.fromkeys(str(cue).strip() for cue in cues if str(cue).strip()))[:12]
        activated: dict[str, dict[str, Any]] = {}
        seed_ids: list[str] = []
        for cue in clean_cues:
            for card in self.search(cue, limit=bounded_limit):
                entry = activated.setdefault(card["id"], {"term": card, "triggered_by": [], "paths": []})
                if cue not in entry["triggered_by"]:
                    entry["triggered_by"].append(cue)
                if card["id"] not in seed_ids:
                    seed_ids.append(card["id"])
        for seed_id in seed_ids:
            for edge in self.neighbors.get(seed_id, []):
                neighbor_id = edge["target_id"] if edge["source_id"] == seed_id else edge["source_id"]
                neighbor = self.read(neighbor_id)
                if not neighbor:
                    continue
                entry = activated.setdefault(neighbor_id, {"term": neighbor, "triggered_by": [], "paths": []})
                path = {"from": seed_id, "relation": edge["relation"]}
                if path not in entry["paths"]:
                    entry["paths"].append(path)

        return {
            "context": context.strip(),
            "cues": clean_cues,
            "activations": list(activated.values())[:bounded_limit],
            "families": [],
            "snapshot_exported_at": self.exported_at,
        }
