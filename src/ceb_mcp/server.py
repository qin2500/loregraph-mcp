from __future__ import annotations

from typing import Annotated

import anyio
from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .client import CebClient

# ponytail: fixed poll cadence/budget rather than adaptive backoff. Bumped after real e2e
# testing showed extraction against the home LLM box commonly takes minutes, not seconds —
# revisit (e.g. adaptive backoff, or a separate "poll status" tool) if 5 min still isn't enough.
_CAPTURE_POLL_INTERVAL_S = 3.0
_CAPTURE_POLL_BUDGET_S = 300.0


def build_server(client: CebClient) -> MCPServer:
    mcp = MCPServer("ceb-mcp")

    @mcp.tool()
    async def retrieve(
        query: Annotated[
            str,
            Field(
                description=(
                    "Natural-language search query — a topic, entity name, question, or "
                    "keywords. 1-4000 characters."
                )
            ),
        ],
        k: Annotated[
            int, Field(description="Max number of ranked episodes to return. 1-50, default 8.")
        ] = 8,
    ) -> dict:
        """Search this person's personal knowledge graph (their captured notes).

        This is the default, go-to tool for almost every lookup — "what do I know about X",
        "find my notes on Y", checking a fact before answering, etc. It's a plain ranked
        search (no LLM call), so it's fast and has no risk of timing out. Returns ranked
        episodes (the matching notes) plus structured facts extracted from them and a
        rendered_text context blob.

        Caveat: this does NOT include notes that are still being captured — a note is only
        searchable once its `capture` call reports status "done". If you just captured
        something and it's not showing up yet, that's expected; it may still be processing.
        """
        return await client.retrieve(query, k)

    # answer is disabled for now: retrieve covers ~99.9% of usage and doesn't risk the
    # Cloudflare edge timeout answer can hit under the current slow LLM. client.answer()
    # is still there to re-enable by adding a @mcp.tool() wrapper back here.

    @mcp.tool()
    async def list_episodes(
        offset: Annotated[
            int, Field(description="Number of episodes to skip, for pagination. Default 0.")
        ] = 0,
        limit: Annotated[
            int,
            Field(
                description="Max episodes to return, 1-500 (capped server-side). Default 100."
            ),
        ] = 100,
    ) -> dict:
        """Browse this person's captured notes in order, without a search query.

        Use this for "what have I captured recently" / "show me everything" / auditing what's
        in the graph — anything where you want a list, not a targeted search. If you're
        looking for something specific, use `retrieve` instead; it's the better fit for
        "find X" style requests.
        """
        return await client.list_episodes(offset, limit)

    @mcp.tool()
    async def get_episode(
        episode_id: Annotated[
            str,
            Field(
                description=(
                    "The episode id to fetch, e.g. one seen in the results of `retrieve`, "
                    "`list_episodes`, or a prior `capture` call (looks like 'ep_...')."
                )
            ),
        ],
    ) -> dict:
        """Fetch one specific captured note by its episode id, with full detail.

        Use this only after you already have an episode id from `retrieve`, `list_episodes`,
        or `capture` and want that note's complete record (full text, extracted entities,
        facts, media, timestamps) rather than the summary those tools already gave you. Not
        for searching — you need the id first. 404s if the id doesn't exist or isn't yours.
        """
        return await client.get_episode(episode_id)

    @mcp.tool()
    async def capture(
        text: Annotated[
            str, Field(description="The note text to save. 1-20,000 characters.")
        ],
    ) -> dict:
        """Save a new note into this person's personal knowledge graph.

        Use this whenever the user wants something remembered/logged/saved for later — the
        write counterpart to `retrieve`. Note this is slow: it waits (up to ~5 minutes —
        extraction against the backend's LLM genuinely takes that long) for ingestion to
        finish so a "done" result is actually searchable via `retrieve` right after. Warn the
        user this may take a while rather than going silent.

        If ingestion is still running past that budget, this returns the last known status
        honestly (status "queued" or "processing") instead of claiming the note is done — in
        that case tell the user it's still processing and that `retrieve` may not find it
        yet; don't retry `capture` itself, the note was already accepted. Media attachments
        are not supported yet — the backend has no presigned-upload endpoint for them, so
        only plain text can be captured.
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
