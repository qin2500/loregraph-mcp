from __future__ import annotations

import getpass
import os
import sys

import anyio

from .client import CebClient
from .config import DEFAULT_PORT, config_path, load_config, save_config
from .server import build_server

BASE_URL = os.environ.get("CEB_MCP_BASE_URL", "https://ceb-backend.anthonyqin.me")


def _prompt_credentials() -> dict:
    client_id = input("Client ID: ").strip()
    client_secret = getpass.getpass("Client Secret: ").strip()
    return {"client_id": client_id, "client_secret": client_secret}


def _prompt_port() -> int:
    raw = input(f"Port [{DEFAULT_PORT}]: ").strip()
    return int(raw) if raw else DEFAULT_PORT


def main() -> None:
    config = load_config()
    if config is None:
        print(f"No config found at {config_path()} — let's set it up.")
        config = _prompt_credentials()
        save_config(config)
    else:
        if input("Update service token? [y/N]: ").strip().lower() == "y":
            config.update(_prompt_credentials())
            save_config(config)

    port = _prompt_port()
    client = CebClient(BASE_URL, config["client_id"], config["client_secret"])

    async def self_check() -> None:
        try:
            me = await client.me()
        except Exception as exc:
            print(f"Auth check against {BASE_URL}/v1/me failed: {exc}", file=sys.stderr)
            print("Re-run and answer 'y' to update your service token.", file=sys.stderr)
            await client.aclose()
            sys.exit(1)
        print(f"Authenticated as {me['id']}")

    anyio.run(self_check)

    mcp = build_server(client)
    print(f"Starting ceb-mcp on http://127.0.0.1:{port}/mcp")
    mcp.run(transport="streamable-http", host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
