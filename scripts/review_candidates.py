#!/usr/bin/env python3
"""Record a human keep/reject decision for one generated candidate."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "runs" / "candidates.jsonl")
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--index", type=int)
    parser.add_argument("--verdict", choices=("keep", "reject"))
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    rows = load(args.input)
    if args.show:
        for index, row in enumerate(rows):
            print(f"[{index}] {row.get('request', row.get('topic', ''))}\n    {row.get('output', '')}\n")
    if args.index is None:
        return 0
    if args.verdict is None or not 0 <= args.index < len(rows):
        raise SystemExit("provide a valid --index and --verdict")
    rows[args.index]["review"] = {
        "verdict": args.verdict,
        "note": args.note.strip(),
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
    }
    args.input.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps(rows[args.index]["review"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
