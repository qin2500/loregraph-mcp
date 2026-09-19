# ceb-mcp

Local MCP server exposing the `ceb-backend` personal knowledge-graph API as MCP tools, over
Streamable HTTP on `localhost`. `ceb-backend` is a home-server-hosted API reached through a
Cloudflare Tunnel + Cloudflare Access; this server is just an authenticated HTTP client of it —
it doesn't run any of that backend's own code.

## Install

```
git clone <this repo's URL>
cd loregraph-mcp
pip install -e .
```

This registers a `ceb-mcp` console command (see the `[project.scripts]` entry in
`pyproject.toml`).

## First run

```
ceb-mcp
```

You'll be prompted for your personal Cloudflare Access **Client ID** and **Client Secret** (the
service token pair created for you in the Cloudflare Zero Trust dashboard — ask whoever manages
the backend for yours if you don't have one). These are saved locally to:

- Windows: `%APPDATA%\ceb-mcp\config.json`
- macOS/Linux: `~/.config/ceb-mcp/config.json`

They are never committed or sent anywhere except as auth headers to the backend.

## Every subsequent run

```
ceb-mcp
Update service token? [y/N]:   <- Enter to keep your saved token
Port [58632]:                  <- Enter to use the default port
```

Two Enter presses and the server is up. It stays running in that terminal (Ctrl+C to stop) and
prints `Authenticated as <your user id>` once its startup auth check against `/v1/me` succeeds —
if that check fails, it exits immediately with the error instead of starting a broken server.

## Connecting an MCP client

Point Claude Desktop or Claude Code at the running server as a Streamable HTTP MCP server, e.g.
in Claude Desktop's `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ceb": {
      "url": "http://localhost:58632/mcp"
    }
  }
}
```

Swap the port if you chose a different one at startup.

## Tools exposed

Each tool's docstring in `server.py` tells the calling model when to reach for it vs. the
others (that's what an MCP client actually sees, not this table) — this is just a quick
reference for a human reader.

| Tool | Maps to | When it's used | Notes |
|---|---|---|---|
| `retrieve(query, k=8)` | `POST /v1/retrieve` | The default, go-to search — "what do I know about X". | No LLM call, fast. Excludes captures still queued/processing. `query`: 1-4000 chars. `k`: 1-50, default 8. |
| `list_episodes(offset=0, limit=100)` | `GET /v1/episodes` | Browsing everything captured, not a targeted search. | Paginated; `limit` capped at 500 server-side. |
| `get_episode(episode_id)` | `GET /v1/episodes/{id}` | Fetching full detail once you already have an id (from `retrieve`/`list_episodes`/`capture`). | 404 if not found or not yours. |
| `capture(text)` | `POST /v1/capture` + polls `GET /v1/capture/{job_id}` | Saving a new note — the write counterpart to `retrieve`. | `text`: 1-20,000 chars. Blocks up to ~5 min until ingestion is `done` (extraction against the home LLM box is genuinely this slow), so a successful result is actually searchable via `retrieve` right after. Returns the honest `queued`/`processing` status if it's still running past that budget — never claims "done" prematurely. |

`GET /v1/me` is used only internally as the startup auth check, not exposed as a tool.

`answer` (`POST /v1/answer`) is disabled for now — `retrieve` covers the vast majority of use
cases and doesn't risk the Cloudflare edge timeout `answer` can hit under the current slow LLM.
`CebClient.answer()` still exists in `client.py`; re-enable by adding a `@mcp.tool()` wrapper
back in `server.py`.

## Config

- `CEB_MCP_BASE_URL` env var overrides the backend base URL (defaults to
  `https://ceb-backend.anthonyqin.me`).
- Media attachments in `capture` are not supported yet — `ceb-backend` has no presigned-upload
  endpoint for them yet. Text-only captures work today.

## Running the self-check

```
python tests/test_capture_poll.py
```

Exercises the `capture` tool's poll-until-done and poll-timeout logic against a fake backend
client (no network calls, no real backend needed).
