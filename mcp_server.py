"""Local stdio MCP server for the bundled Abstract Meme corpus snapshot."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from local_corpus import LocalCorpus


corpus = LocalCorpus.from_file()
server = FastMCP(
    "Chinese Abstract Meme Corpus",
    instructions=(
        "This server exposes a local, versioned Chinese internet-meme corpus. "
        "Use it for wording, examples, variants, and associations; do not use it as a current-facts source."
    ),
)


@server.tool(name="corpus.search")
def corpus_search(query: str, limit: int = 64) -> dict:
    """Find confirmed entries through a term, recorded variant, phrase, or usage clue."""
    return {"query": query, "terms": corpus.search(query, limit=limit), "snapshot_exported_at": corpus.exported_at}


@server.tool(name="corpus.read")
def corpus_read(term_id: str) -> dict:
    """Read one confirmed corpus entry in full."""
    term = corpus.read(term_id)
    return {"found": term is not None, "term_id": term_id, "term": term}


@server.tool(name="corpus.activate")
def corpus_activate(context: str, cues: list[str], limit: int = 24) -> dict:
    """Activate entries from concrete contextual cues supplied by the calling agent."""
    return corpus.activate(context, cues, limit=limit)


if __name__ == "__main__":
    server.run(transport="stdio")
