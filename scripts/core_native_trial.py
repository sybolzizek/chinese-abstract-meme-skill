#!/usr/bin/env python3
"""Import the live corpus into nous_engine without collapsing its card structure."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID


CORE_PROJECT = Path(r"D:\coding\新建文件夹\AI-Animation-Studio")
if str(CORE_PROJECT) not in sys.path:
    sys.path.insert(0, str(CORE_PROJECT))

from nous_engine.core.agent.knowledge import InMemoryKnowledgeBackend  # noqa: E402
from nous_engine.core.agent.knowledge.models import KnowledgeEntry, KnowledgeFilter  # noqa: E402


def fetch_graph(base_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url.rstrip("/") + "/v1/graph", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


async def run(graph: dict[str, Any]) -> dict[str, Any]:
    backend = InMemoryKnowledgeBackend()
    await backend.initialize()
    try:
        root = await backend.create(
            KnowledgeEntry(
                user_id="topology-trial",
                namespace="abstract-trial",
                title="abstract corpus",
                abstract="The corpus in its native card structure.",
                source_type="corpus_root",
                index_data={"native": {"kind": "abstract_corpus"}},
            )
        )
        term_to_entry: dict[str, str] = {}
        source_id_to_entry: dict[str, str] = {}
        cards: list[dict[str, Any]] = []
        for item in graph.get("terms", []):
            entry = await backend.create(
                KnowledgeEntry(
                    user_id="topology-trial",
                    namespace="abstract-trial",
                    parent_id=root.id,
                    title=str(item.get("term") or ""),
                    abstract=str(item.get("explanation") or ""),
                    content=json.dumps(
                        {
                            "examples": item.get("examples") or [],
                            "derivations": item.get("derivations") or [],
                            "sources": item.get("sources") or [],
                        },
                        ensure_ascii=False,
                    ),
                    content_type="json",
                    source_type="corpus_card",
                    index_data={
                        "native": {
                            "term_id": str(item.get("id") or ""),
                            "term": item.get("term") or "",
                            "examples": item.get("examples") or [],
                            "derivations": item.get("derivations") or [],
                            "sources": item.get("sources") or [],
                            "status": item.get("status") or "",
                            "version": item.get("version"),
                        }
                    },
                )
            )
            cards.append(item)
            term_to_entry.setdefault(str(item.get("term") or ""), str(entry.id))
            source_id_to_entry[str(item.get("id") or "")] = str(entry.id)

        edge_count = 0
        for relation in graph.get("relations", []):
            source = source_id_to_entry.get(str(relation.get("source_id") or ""))
            target = source_id_to_entry.get(str(relation.get("target_id") or ""))
            if source and target:
                await backend.relate(UUID(source), UUID(target), str(relation.get("relation") or "references"), note=str(relation.get("note") or ""))
                edge_count += 1
        for item in cards:
            source = source_id_to_entry.get(str(item.get("id") or ""))
            if not source:
                continue
            for surface in item.get("derivations") or []:
                target = term_to_entry.get(str(surface or ""))
                if target and target != source:
                    await backend.relate(UUID(source), UUID(target), "derivation", note="Declared in the corpus card.")
                    edge_count += 1

        imported = await backend.filter(KnowledgeFilter(namespace="abstract-trial", source_type="corpus_card", limit=2000))
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "term_count": len(cards),
            "imported_card_count": len(imported),
            "preserved_explicit_relation_count": len(graph.get("relations", [])),
            "edge_count": edge_count,
        }
    finally:
        await backend.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=os.getenv("ABSTRACT_CORPUS_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "runs" / "core-native-trial.json")
    args = parser.parse_args()
    result = asyncio.run(run(fetch_graph(args.api_base)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
