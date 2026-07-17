#!/usr/bin/env python3
"""Forward-test a model against declared material and a corpus context pack."""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_local_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def read_json(path: Path | None) -> dict:
    return {} if path is None else json.loads(path.read_text(encoding="utf-8"))


def build_prompt(request: str, scene: str, facts: str, corpus: dict) -> tuple[str, str]:
    system = "".join(
        [
            "只处理用户给出的材料。",
            "返回用户要求的成品，不解释、不总结、不声明反串。",
            "用户要评论时，写成刷到内容后会直接发出的短回复，不写对内容的介绍、分析或传播判断。",
            "不要复述‘短视频、传播、网友、节目、现场’这类背景词，除非用户要求它们出现在成品里。",
            "默认不超过二十四个汉字或等量字符。",
            "语料卡只是可选材料；不相关就不用。",
            "不得补充材料中没有的事实。",
            "没有合适输出时只返回 [skip]。",
        ]
    )
    user = json.dumps(
        {"request": request, "scene": scene, "facts": facts, "corpus": corpus.get("cards", [])},
        ensure_ascii=False,
    )
    return system, user


def call(base_url: str, api_key: str, model: str, system: str, user: str, temperature: float) -> tuple[str, dict]:
    request = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions",
        data=json.dumps({"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}], "temperature": temperature}, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"model HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"model network error: {exc.reason}") from exc
    try:
        return payload["choices"][0]["message"]["content"].strip(), payload.get("usage", {})
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("model response has no content") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request")
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--scene")
    parser.add_argument("--scene-file", type=Path)
    parser.add_argument("--facts")
    parser.add_argument("--facts-file", type=Path)
    parser.add_argument("--context", type=Path)
    parser.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    parser.add_argument("--base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--temperature", type=float, default=0.8)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "candidates.jsonl")
    args = parser.parse_args()
    request_text = args.request_file.read_text(encoding="utf-8").strip() if args.request_file else (args.request or "").strip()
    scene_text = args.scene_file.read_text(encoding="utf-8").strip() if args.scene_file else (args.scene or "").strip()
    facts_text = args.facts_file.read_text(encoding="utf-8").strip() if args.facts_file else (args.facts or "").strip()
    if not request_text or not facts_text:
        parser.error("provide --request/--request-file and --facts/--facts-file")
    if not scene_text:
        print("[skip]")
        return 0
    corpus = read_json(args.context)
    system, user = build_prompt(request_text, scene_text, facts_text, corpus)
    if args.dry_run:
        print(json.dumps({"system": system, "user": json.loads(user)}, ensure_ascii=False, indent=2))
        return 0
    load_local_env()
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("DEEPSEEK_API_KEY is not configured", file=sys.stderr)
        return 2
    output, usage = call(args.base_url, api_key, args.model, system, user, args.temperature)
    record = {"created_at": datetime.now(timezone.utc).isoformat(), "request": request_text, "scene": scene_text, "facts": facts_text, "context": corpus, "model": args.model, "output": output, "usage": usage, "review": None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
