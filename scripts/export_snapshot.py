"""Export confirmed V2 corpus material into the portable public snapshot."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "corpus.json"


def fetch_graph(api_base: str) -> dict:
    url = f"{api_base.rstrip('/')}/graph"
    with urlopen(url, timeout=30) as response:  # nosec B310 - explicit operator-provided URL
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export confirmed AbstractTV corpus into a standalone snapshot.")
    parser.add_argument("--api-base", default="http://127.0.0.1:8010/v2")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    graph = fetch_graph(args.api_base)
    terms = list(graph.get("terms", []))
    term_ids = {row.get("id") for row in terms}
    snapshot = {
        "format": "abstract-meme-corpus/v1",
        "exported_at": datetime.now(UTC).isoformat(),
        "terms": terms,
        "relations": [
            row
            for row in graph.get("relations", [])
            if row.get("source_id") in term_ids and row.get("target_id") in term_ids
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(terms)} terms and {len(snapshot['relations'])} relations to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
