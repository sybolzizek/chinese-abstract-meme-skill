#!/usr/bin/env python3
"""Export only human rejection notes for a later forward test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "candidates.jsonl")
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "feedback.txt")
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    lines = []
    for row in rows:
        review = row.get("review") or {}
        if review.get("verdict") == "reject" and review.get("note"):
            lines.append(f"输入：{row.get('request', row.get('topic', ''))}\n失败样本：{row.get('output', '')}\n问题：{review['note']}")
    if not lines:
        raise SystemExit("no rejected candidates with notes")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
