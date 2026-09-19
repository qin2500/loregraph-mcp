from __future__ import annotations

import anyio
from mcp.server.mcpserver import MCPServer

from .client import CebClient

# ponytail: fixed poll cadence/budget rather than adaptive backoff — revisit if ingestion
# routinely takes longer than ~60s and callers start seeing "processing" too often.
_CAPTURE_POLL_INTERVAL_S = 1.5
_CAPTURE_POLL_BUDGET_S = 60.0


def build_server(client: CebClient) -> MCPServer:
    mcp = MCPServer("ceb-mcp")

    @mcp.tool()
    async def retrieve(query: str, k: int = 8) -> dict:
        """Search the personal knowledge graph. Excludes captures still queued/processing."""
        return await client.retrieve(query, k)

    @mcp.tool()
    async def answer(question: str, k: int = 8) -> dict:
        """Answer a question from the personal knowledge graph, synthesized by an LLM."""
        return await client.answer(question, k)

    @mcp.tool()
    async def list_episodes(offset: int = 0, limit: int = 100) -> dict:
        """List captured episodes, paginated (limit capped at 500 server-side)."""
        return await client.list_episodes(offset, limit)

    @mcp.tool()
    async def get_episode(episode_id: str) -> dict:
        """Fetch a single episode by id."""
        return await client.get_episode(episode_id)

    @mcp.tool()
    async def capture(text: str) -> dict:
        """Capture a text note into the personal knowledge graph.

        Waits (up to ~60s) for ingestion to finish so a "done" result is actually
        searchable via retrieve/answer. If ingestion is still running past that budget,
        returns the last known status honestly (status "queued" or "processing") instead
        of claiming the note is done. Media attachments are not supported yet — the
        backend has no presigned-upload endpoint for them.
        """
        status = await client.capture_start(text)
        job_id = status["job_id"]
        elapsed = 0.0
        while status["status"] not in ("done", "failed") and elapsed < _CAPTURE_POLL_BUDGET_S:
            await anyio.sleep(_CAPTURE_POLL_INTERVAL_S)
            elapsed += _CAPTURE_POLL_INTERVAL_S
            status = await client.capture_status(job_id)
        return status

    return mcp
