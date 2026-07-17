#!/usr/bin/env python3
"""Build a disposable topology from the live corpus with nous_engine's pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CORE_PROJECT = Path(r"D:\coding\新建文件夹\AI-Animation-Studio")
if str(CORE_PROJECT) not in sys.path:
    sys.path.insert(0, str(CORE_PROJECT))

from nous_engine.core.agent.knowledge import InMemoryKnowledgeBackend  # noqa: E402
from nous_engine.core.agent.knowledge.pipeline import ingest_document  # noqa: E402
from nous_engine.core.agent.knowledge.models import KnowledgeFilter  # noqa: E402


def load_local_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


class ChatLLM:
    def __init__(self, *, api_key: str, base_url: str, model: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.default_model = model
        self.calls = 0

    async def generate(
        self,
        messages: list[dict[str, str]],
        *,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        **_: Any,
    ) -> str:
        self.calls += 1
        print(f"model call {self.calls}", flush=True)
        return await asyncio.to_thread(self._call, messages, temperature, max_tokens)

    def _call(self, messages: list[dict[str, str]], temperature: float, max_tokens: int | None) -> str:
        body: dict[str, Any] = {"model": self.default_model, "messages": messages, "temperature": temperature}
        if max_tokens:
            body["max_tokens"] = max_tokens
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        return str(payload["choices"][0]["message"]["content"] or "")


def fetch_graph(base_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url.rstrip("/") + "/v1/graph", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def render_corpus(graph: dict[str, Any]) -> str:
    rows: list[str] = []
    for item in graph.get("terms", []):
        rows.append(
            json.dumps(
                {
                    "id": item.get("id"),
                    "term": item.get("term"),
                    "explanation": item.get("explanation"),
                    "examples": (item.get("examples") or [])[:3],
                    "derivations": (item.get("derivations") or [])[:16],
                },
                ensure_ascii=False,
            )
        )
    return "\n".join(rows)


async def run(args: argparse.Namespace) -> dict[str, Any]:
    graph = fetch_graph(args.api_base)
    text = render_corpus(graph)
    backend = InMemoryKnowledgeBackend()
    await backend.initialize()
    llm = ChatLLM(api_key=args.api_key, base_url=args.base_url, model=args.model)
    try:
        entries = await ingest_document(
            text=text,
            title="abstract corpus",
            source_url="corpus://abstract-meme/live-graph",
            user_id="topology-trial",
            namespace="abstract-trial",
            backend=backend,
            llm=llm,
            extra_index={"source": "live corpus graph"},
            pass2_concurrency=args.concurrency,
        )
        maps = await backend.filter(
            KnowledgeFilter(
                namespace="abstract-trial",
                source_type="topology_artifact",
                index_matches={"topology_artifact": "topology_map"},
                limit=1,
            )
        )
        map_body: dict[str, Any] = {}
        if maps:
            map_body = json.loads(maps[0].content)
        return {
            "term_count": len(graph.get("terms", [])),
            "relation_count": len(graph.get("relations", [])),
            "topology_entry_count": len(entries),
            "model_calls": llm.calls,
            "topology": map_body,
        }
    finally:
        await backend.close()


def main() -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default=os.getenv("ABSTRACT_CORPUS_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    parser.add_argument("--api-key", default=os.getenv("DEEPSEEK_API_KEY", ""))
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "core-topology-trial.json")
    args = parser.parse_args()
    if not args.api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not configured")
    result = asyncio.run(run(args))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "topology"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
