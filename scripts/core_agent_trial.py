#!/usr/bin/env python3
"""Run the existing nous_engine AgentRuntime with a read-only abstract corpus tool surface."""

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

from nous_engine.core.agent.assistant.plugin import AssistantAgentPlugin  # noqa: E402
from nous_engine.core.agent.runtime import AgentRuntime  # noqa: E402
from nous_engine.core.agent.session import AgentSession  # noqa: E402
from nous_engine.core.agent.skills import MarkdownSkillLoader  # noqa: E402
from nous_engine.core.agent.tool_spec import ToolSpec  # noqa: E402


CORPUS_TOOLS = {
    "corpus.cards": ToolSpec(
        name="corpus.cards",
        description="Read one stable page of corpus cards. This is pagination, not search or ranking.",
        arguments={"cursor": "Zero-based page offset.", "limit": "1-24 cards per page."}, authority="abstract-corpus", side_effect="none", kind="mcp_read",
    ),
    "corpus.open": ToolSpec(
        name="corpus.open",
        description="Open exact corpus cards by term or known variant.",
        arguments={"terms": "One term/variant or a list of them."}, authority="abstract-corpus", side_effect="none", kind="mcp_read",
    ),
    "corpus.lookup": ToolSpec(
        name="corpus.lookup",
        description="Open a small set of exact candidate surfaces the agent already has in mind. No ranking, similarity, or forced relation is applied.",
        arguments={"candidates": "A list of exact terms or variants to check."}, authority="abstract-corpus", side_effect="none", kind="mcp_read",
    ),
}


def load_local_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def fetch_graph(base_url: str) -> dict[str, Any]:
    with urllib.request.urlopen(base_url.rstrip("/") + "/v1/graph", timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _needs_freshness_review(request: str) -> bool:
    return any(
        marker in request
        for marker in (
            "最近", "当前", "这届", "今天", "本周", "正在流行", "最新",
            "世界杯", "世界赛", "MSI", "决赛", "赛事",
        )
    )


def _needs_tone_review(request: str) -> bool:
    return any(marker in request for marker in ("串一下", "串一句", "回一句", "短句", "怎么回"))


def _evidence_packet(tool_results: list[dict[str, Any]], request: str = "") -> dict[str, Any]:
    """Reduce raw search output to readable, higher-confidence claim rows."""
    facts: list[dict[str, Any]] = []
    leads: list[dict[str, Any]] = []
    for item in tool_results:
        if item.get("tool") != "web_search":
            continue
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        payload = data.get("data") if isinstance(data.get("data"), dict) else data
        raw_rows = payload.get("results", []) if isinstance(payload, dict) else []
        for raw in raw_rows:
            title = str(raw.get("title") or "").strip()
            snippet = str(raw.get("snippet") or raw.get("preview") or "").strip()
            if not title and not snippet:
                continue
            rank = str(raw.get("source_rank") or "general_web")
            broken = snippet.count("�") >= 2 or snippet.count("鈥") >= 2 or len(snippet) < 24
            if broken:
                continue
            row = {
                "title": title[:240],
                "claim_text": snippet[:1200],
                "url": str(raw.get("url") or "").strip(),
                "host": raw.get("source_host") or "",
                "source_rank": rank,
            }
            (facts if rank in {"primary_or_high_confidence", "reputable_media_or_reference"} else leads).append(row)
    return {"facts": facts[:12], "leads": leads[:12], "fact_count": len(facts), "lead_count": len(leads)}


class ChatLLM:
    def __init__(self, api_key: str, base_url: str, model: str) -> None:
        self.api_key, self.base_url, self.default_model = api_key, base_url.rstrip("/"), model

    async def generate(self, messages: list[dict[str, str]], *, temperature: float = 0.5, max_tokens: int | None = None, **_: Any) -> str:
        return await asyncio.to_thread(self._call, messages, temperature, max_tokens)

    def _call(self, messages: list[dict[str, str]], temperature: float, max_tokens: int | None) -> str:
        payload: dict[str, Any] = {"model": self.default_model, "messages": messages, "temperature": temperature}
        if max_tokens:
            payload["max_tokens"] = max_tokens
        request = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=180) as response:
            result = json.loads(response.read().decode("utf-8"))
        content = str(result["choices"][0]["message"]["content"] or "")
        trace_path = os.getenv("ABSTRACT_TRIAL_RAW_TRACE")
        if trace_path:
            with Path(trace_path).open("a", encoding="utf-8") as trace:
                trace.write(json.dumps({"messages": messages, "response": content}, ensure_ascii=False) + "\n")
        return content


async def _rewrite_search_queries(llm: ChatLLM, request: str) -> list[str]:
    text = await llm.generate(
        [
            {
                "role": "system",
                "content": "把用户请求改写成最多两个适合搜索引擎的关键词句。只输出 JSON 字符串数组，不回答问题，不添加请求中没有的人名、赛事、时间或事实。",
            },
            {"role": "user", "content": request},
        ],
        temperature=0,
        max_tokens=300,
    )
    try:
        values = json.loads(text)
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    if not isinstance(values, list):
        return []
    return list(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))[:2]


class AbstractTrialPlugin(AssistantAgentPlugin):
    domain = "abstract_trial"

    def __init__(self, graph: dict[str, Any]) -> None:
        super().__init__(
            tools=CORPUS_TOOLS,
            system_prompt=(
                "遵守已加载的 chinese-abstract-meme skill。涉及最近、当前、这届、今天或正在流行的事实时，"
                "先用 time.now 和 web_search；搜索摘要不能证明的内容，继续 web_fetch。只把工具材料明确支持的"
                "人物、时间、比分、数据写成事实；材料不足就说未核实，不要用记忆补齐，也不要先说‘我去搜’再不调用工具。"
                "工具返回后不要向用户播报搜索过程，也不要以‘我再搜一下’或待办计划收尾；直接回答，或明确说仍未核实。"
                "用户说‘串一下’时给短一点的成品。"
                "纯串时先根据场景自己想几组候选词面，再用 corpus.lookup 精确核对；只有确实合适才采用，"
                "不要输出候选清单，也不要因为查到卡片就硬塞。"
                "搜索结果只是线索；比分、排名、日期和人物经历优先用官方记录或明确署名的可靠报道，并尽量交叉核对。"
                "标题、摘要、SEO页面和不明镜像不能单独支撑事实，来源不可靠或互相矛盾时删掉该细节。"
            ),
        )
        self.graph = graph
        self.by_surface: dict[str, list[dict[str, Any]]] = {}
        self.by_id = {str(item.get("id")): item for item in graph.get("terms", [])}
        for item in graph.get("terms", []):
            for surface in [item.get("term"), *(item.get("derivations") or [])]:
                text = str(surface or "").strip()
                if text:
                    self.by_surface.setdefault(text, []).append(item)

    def _skill_loader(self) -> MarkdownSkillLoader:
        return MarkdownSkillLoader(ROOT, ({"key": "SKILL", "title": "Chinese abstract meme", "mounted": True},))

    def create_state(self) -> dict[str, Any]:
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        return {
            "_assistant_enabled_tool_groups": ["web", "custom"],
            "active_skill_docs": [{"key": "SKILL", "title": "Chinese abstract meme", "source": "local", "content": skill}],
        }

    @staticmethod
    def _page(args: dict[str, Any]) -> tuple[int, int]:
        try:
            cursor = max(0, int(args.get("cursor") or 0))
        except (TypeError, ValueError):
            cursor = 0
        try:
            limit = min(24, max(1, int(args.get("limit") or 12)))
        except (TypeError, ValueError):
            limit = 12
        return cursor, limit

    @staticmethod
    def _card(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "term": item.get("term"),
            "explanation": item.get("explanation"),
            "examples": item.get("examples") or [],
            "derivations": item.get("derivations") or [],
        }

    def explicit_surfaces(self, text: str, *, limit: int = 8) -> list[str]:
        """Return only exact multi-character surfaces literally present in text."""
        candidates = [surface for surface in self.by_surface if len(surface) >= 2 and surface in text]
        return sorted(candidates, key=lambda value: (-len(value), value))[:limit]

    async def _exec_corpus_cards(self, args: dict[str, Any], _state: Any) -> dict[str, Any]:
        cursor, limit = self._page(args)
        ordered = sorted(
            self.graph.get("terms", []),
            key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")),
        )
        page = ordered[cursor:cursor + limit]
        return {
            "ok": True,
            "data": {
                "cards": [self._card(item) for item in page],
                "cursor": cursor,
                "next_cursor": cursor + len(page) if cursor + len(page) < len(ordered) else None,
                "total": len(ordered),
            },
        }

    async def _exec_corpus_open(self, args: dict[str, Any], _state: Any) -> dict[str, Any]:
        raw = args.get("terms") or []
        terms = [raw] if isinstance(raw, str) else raw
        cards: list[dict[str, Any]] = []
        seen: set[str] = set()
        for term in terms if isinstance(terms, list) else []:
            key = str(term).strip()
            candidates = [self.by_id[key]] if key in self.by_id else self.by_surface.get(key, [])
            for item in candidates:
                item_id = str(item.get("id"))
                if item_id not in seen:
                    cards.append(self._card(item))
                    seen.add(item_id)
        requested = [str(term).strip() for term in terms if str(term).strip()] if isinstance(terms, list) else []
        resolved = {surface for surface in requested if surface in self.by_surface or surface in self.by_id}
        return {
            "ok": True,
            "data": {
                "cards": cards,
                "requested": requested,
                "resolved_surfaces": sorted(resolved),
                "not_found": [surface for surface in requested if surface not in resolved],
            },
        }

    async def _exec_corpus_lookup(self, args: dict[str, Any], _state: Any) -> dict[str, Any]:
        raw = args.get("candidates") or []
        candidates = [raw] if isinstance(raw, str) else raw
        if not isinstance(candidates, list):
            candidates = []
        normalized = []
        seen_surfaces: set[str] = set()
        for value in candidates[:32]:
            surface = str(value).strip()
            if surface and surface not in seen_surfaces:
                normalized.append(surface)
                seen_surfaces.add(surface)
        cards: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for surface in normalized:
            matches = self.by_surface.get(surface, [])
            for item in matches:
                item_id = str(item.get("id"))
                if item_id not in seen_ids:
                    cards.append(self._card(item))
                    seen_ids.add(item_id)
        return {
            "ok": True,
            "data": {
                "requested": normalized,
                "cards": cards,
                "not_found": [surface for surface in normalized if surface not in self.by_surface],
            },
        }



async def run(args: argparse.Namespace) -> dict[str, Any]:
    graph = fetch_graph(args.api_base)
    plugin = AbstractTrialPlugin(graph)
    llm = ChatLLM(args.api_key, args.base_url, args.model)
    runtime = AgentRuntime(llm, plugin, max_tool_rounds=8)
    state = plugin.create_state()
    session = AgentSession(state=state)
    exact_surfaces = plugin.explicit_surfaces(args.request)
    exact_corpus_result: dict[str, Any] | None = None
    if exact_surfaces:
        exact_corpus_result = await plugin._exec_corpus_lookup({"candidates": exact_surfaces}, state)
        state.setdefault("active_skill_docs", []).append(
            {
                "key": "EXACT_CORPUS_CONTEXT",
                "title": "Exact corpus cards for this request",
                "source": "abstract-corpus",
                "content": json.dumps(exact_corpus_result, ensure_ascii=False),
                "max_chars": 10000,
            }
        )
    result = await runtime.run(args.request, session, state)
    if exact_corpus_result is not None:
        result.tool_calls.insert(0, {"tool": "corpus.lookup", "arguments": {"candidates": exact_surfaces}, "preflight": True})
        result.tool_results.insert(0, {"tool": "corpus.lookup", "data": exact_corpus_result})
    if _needs_freshness_review(args.request) and result.ok:
        has_web = any(str(call.get("tool")) == "web_search" for call in result.tool_calls)
        existing_queries = {
            str(call.get("arguments", {}).get("query") or "")
            for call in result.tool_calls
            if str(call.get("tool")) == "web_search"
        }
        queries = [args.request]
        queries.extend(await _rewrite_search_queries(llm, args.request))
        for query in list(dict.fromkeys(queries)):
            if query in existing_queries:
                continue
            preflight_args = {
                "query": query,
                "max_results": 8,
                "fetch_preview": True,
                "time_range": "month" if any(marker in args.request for marker in ("最近", "当前", "这届", "今天", "本周", "正在流行", "最新")) else "",
            }
            preflight = await plugin._execute_web_search(preflight_args)
            result.tool_calls.append({"tool": "web_search", "arguments": preflight_args, "preflight": True})
            result.tool_results.append({"tool": "web_search", "data": preflight})
        web_rows = [row for row in result.tool_results if str(row.get("tool")) == "web_search"]
        has_search_evidence = any(
            bool(
                isinstance(row.get("data"), dict)
                and isinstance(row["data"].get("data"), dict)
                and row["data"]["data"].get("results")
            )
            for row in web_rows
        )
        if not web_rows or not has_search_evidence:
            result.response = "目前检索材料不足，无法核实。"
            return {
                "request": args.request,
                "answer": result.response,
                "ok": result.ok,
                "error": result.error,
                "tool_rounds": result.tool_rounds,
                "tool_calls": result.tool_calls,
                "tool_results": result.tool_results,
            }
        packet = _evidence_packet(result.tool_results, args.request)
        # Leads remain visible in the trace for later inspection, but cannot drive a factual answer.
        if not packet["facts"]:
            result.response = "目前没有足够可靠的材料，无法核实。"
            return {
                "request": args.request,
                "answer": result.response,
                "ok": result.ok,
                "error": result.error,
                "tool_rounds": result.tool_rounds,
                "tool_calls": result.tool_calls,
                "tool_results": result.tool_results,
            }
        claim_json = await ChatLLM(args.api_key, args.base_url, args.model).generate(
            [
                {
                    "role": "system",
                    "content": (
                        "从给定证据包抽取事实，不创作。只输出与用户请求对象直接相关的 JSON 数组；每项包含 claim、confidence、source。"
                        "claim 只能是证据文字直接支持的陈述，无法确认的放 confidence=uncertain；不要补背景。"
                    ),
                },
                {"role": "user", "content": json.dumps(packet, ensure_ascii=False)},
            ],
            temperature=0,
            max_tokens=1200,
        )
        try:
            parsed_claims = json.loads(claim_json)
            if isinstance(parsed_claims, list):
                packet["claims"] = parsed_claims[:16]
        except (TypeError, ValueError, json.JSONDecodeError):
            packet["claims"] = []
        evidence = json.dumps({"facts": packet["facts"], "claims": packet.get("claims", [])}, ensure_ascii=False)[:14000]
        mining_mode = any(marker in args.request for marker in ("挖掘", "找点", "找一些", "最近流行", "新梗", "热梗"))
        mode_instruction = (
            "这是资料挖掘请求：可以列出最多5条来源明确提到的候选线索，每条写清来源实际说了什么；"
            "不要把‘搜到’改写成‘全网流行’，不要补热度、时间线或事件后果；来源不可靠的只标成待核实，"
            "不要把它包装成定论；不要写‘好的，这是根据工具结果’之类的过程开场，也不要在末尾自行串，除非用户要求串。"
            if mining_mode
            else
            "这是创作请求：只输出用户要的成品，不要把检索过程写成文章。"
        )
        if "串一下" in args.request or "串一句" in args.request:
            mode_instruction += " 用户要的是串，不是资料汇总；保留一到四句，事实够用就停。"
        reviewed = await ChatLLM(args.api_key, args.base_url, args.model).generate(
            [
                {
                    "role": "system",
                    "content": (
                        "你是中文互联网内容编辑。结合工具结果改写草稿，直接回答用户，不要播报搜索过程。"
                        "claims 是事实抽取结果，按 confidence 使用；leads 只是线索，提到时明确说待核实。"
                        "如果证据与用户请求的对象或语境无关，直接说没有找到相关材料，不要把无关新闻硬列出来。"
                        + mode_instruction
                    ),
                },
                {
                    "role": "user",
                    "content": f"用户请求：{args.request}\n\n证据包：{evidence}",
                },
            ],
            temperature=0.1,
            max_tokens=1200,
        )
        if reviewed.strip():
            result.response = reviewed.strip()
    elif _needs_tone_review(args.request) and result.ok and result.response.strip():
        exact_context = ""
        if exact_corpus_result is not None:
            exact_context = "\n\n已精确命中的语料卡片（只能从这里取该梗的意思）：" + json.dumps(
                exact_corpus_result, ensure_ascii=False
            )
        reviewed = await ChatLLM(args.api_key, args.base_url, args.model).generate(
            [
                {
                    "role": "system",
                    "content": (
                        "你是中文互联网短句编辑。把草稿改得像人说的，保留语境和梗感，别播报过程。"
                    ),
                },
                {
                    "role": "user",
                    "content": f"用户请求：{args.request}\n\n草稿：{result.response}{exact_context}",
                },
            ],
            temperature=0.2,
            max_tokens=800,
        )
        if reviewed.strip():
            result.response = reviewed.strip()
    return {
        "request": args.request,
        "answer": result.response,
        "ok": result.ok,
        "error": result.error,
        "tool_rounds": result.tool_rounds,
        "tool_calls": result.tool_calls,
        "tool_results": result.tool_results,
    }


def main() -> int:
    load_local_env()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request")
    parser.add_argument("--request-file", type=Path)
    parser.add_argument("--api-base", default=os.getenv("ABSTRACT_CORPUS_URL", "http://127.0.0.1:8010"))
    parser.add_argument("--base-url", default=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))
    parser.add_argument("--model", default=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"))
    parser.add_argument("--api-key", default=os.getenv("DEEPSEEK_API_KEY", ""))
    parser.add_argument("--output", type=Path, default=ROOT / "runs" / "core-agent-trial.json")
    args = parser.parse_args()
    if args.request_file:
        args.request = args.request_file.read_text(encoding="utf-8").strip()
    if not str(args.request or "").strip():
        parser.error("provide --request or --request-file")
    if not args.api_key:
        raise SystemExit("DEEPSEEK_API_KEY is not configured")
    result = asyncio.run(run(args))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(result["answer"])


if __name__ == "__main__":
    main()
