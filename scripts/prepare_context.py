#!/usr/bin/env python3
"""Build a compact corpus pack for one concrete input.

This is a harness adapter, not a generator.  It can later target the public
MCP service; for now it supports the existing JSON lookup endpoint.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def fetch(base_url: str, text: str) -> list[dict]:
    query = urllib.parse.urlencode({"text": text, "limit": 12})
    url = base_url.rstrip("/") + "/v1/skill/lookup?" + query
    with urllib.request.urlopen(url, timeout=15) as response:  # noqa: S310 - user configured local/public corpus
        payload = json.loads(response.read().decode("utf-8"))
    return payload.get("items", [])


def compact(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "term": item.get("term", ""),
        "explanation": item.get("explanation", ""),
        "examples": item.get("examples", [])[:3],
        "derivations": item.get("derivations", [])[:12],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument("--api-base", default=os.getenv("ABSTRACT_CORPUS_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        items = fetch(args.api_base, args.text)
    except Exception as exc:
        raise SystemExit(f"corpus lookup failed: {exc}") from exc
    payload = {"input": args.text, "cards": [compact(item) for item in items]}
    rendered = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
