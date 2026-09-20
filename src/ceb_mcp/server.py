from __future__ import annotations

from typing import Annotated

from mcp.server.mcpserver import MCPServer
from pydantic import Field

from .client import CebClient


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
        write counterpart to `retrieve`. This returns immediately with a job_id and status
        "queued" — it does NOT wait for ingestion to finish. Extraction against the backend's
        LLM can take minutes, so the note is accepted but not yet searchable via `retrieve`.

        Tell the user it's queued and may take a few minutes, then move on — don't block
        waiting on it. Use `capture_status` later (e.g. if the user asks) to check progress;
        don't retry `capture` itself, the note was already accepted. Media attachments are
        not supported yet — the backend has no presigned-upload endpoint for them, so only
        plain text can be captured.
        """
        return await client.capture_start(text)

    @mcp.tool()
    async def capture_status(
        job_id: Annotated[
            str,
            Field(description="The job_id returned by a prior `capture` call."),
        ],
    ) -> dict:
        """Check on a note's ingestion progress after a prior `capture` call.

        Returns the job's current status: "queued", "processing", "done" (with episode_ids),
        or "failed". Only call this if the user asks about a pending capture's progress —
        don't poll it in a loop waiting for "done"; that reintroduces the blocking behavior
        `capture` deliberately avoids. Once status is "done", `retrieve` will find the note.
        """
        return await client.capture_status(job_id)

    return mcp
