#!/usr/bin/env python3
"""Inspect confirmed corpus cards from a running AbstractTV instance.

This is deliberately read-only. It uses the current V2 API and never invents
terms, rewrites cards, or depends on a local copy of the site database.
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from typing import Any


def request_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310 - explicitly configured corpus host
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="词条、别名或实际出现过的表达")
    parser.add_argument("--api-base", default=os.getenv("ABSTRACT_TV_API", "http://127.0.0.1:8010/v2"))
    parser.add_argument("--limit", type=int, default=12)
    args = parser.parse_args()

    base = args.api_base.rstrip("/")
    params = urllib.parse.urlencode({"q": args.query, "limit": max(1, min(args.limit, 100))})
    rows = request_json(f"{base}/terms/search?{params}")
    cards = []
    for row in rows if isinstance(rows, list) else []:
        term_id = str(row.get("id") or "").strip()
        if not term_id:
            continue
        cards.append(request_json(f"{base}/terms/{urllib.parse.quote(term_id, safe='')}"))
    print(json.dumps({"query": args.query, "cards": cards}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
