"""Self-check for the capture tool's poll-until-done/timeout logic. Run directly:
python tests/test_capture_poll.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import anyio

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from ceb_mcp import server as server_mod  # noqa: E402


class FakeClient:
    def __init__(self, statuses: list[dict]) -> None:
        self._statuses = list(statuses)

    async def capture_start(self, text: str, media: list[str] | None = None) -> dict:
        return self._statuses[0]

    async def capture_status(self, job_id: str) -> dict:
        if len(self._statuses) > 1:
            self._statuses.pop(0)
        return self._statuses[0]


async def test_polls_until_done() -> None:
    fake = FakeClient(
        [
            {"job_id": "1", "status": "queued"},
            {"job_id": "1", "status": "processing"},
            {"job_id": "1", "status": "done", "episode_ids": ["e1"]},
        ]
    )
    server_mod._CAPTURE_POLL_INTERVAL_S = 0  # no need to actually wait in a test
    mcp = server_mod.build_server(fake)  # type: ignore[arg-type]
    result = await mcp.call_tool("capture", {"text": "hello"})
    assert not result.is_error, result.content
    payload = json.loads(result.content[0].text)
    assert payload["status"] == "done", payload
    assert payload["episode_ids"] == ["e1"], payload


async def test_gives_up_honestly_after_budget() -> None:
    fake = FakeClient([{"job_id": "1", "status": "processing"}])
    server_mod._CAPTURE_POLL_INTERVAL_S = 0
    server_mod._CAPTURE_POLL_BUDGET_S = 0  # give up immediately
    mcp = server_mod.build_server(fake)  # type: ignore[arg-type]
    result = await mcp.call_tool("capture", {"text": "hello"})
    assert not result.is_error, result.content
    payload = json.loads(result.content[0].text)
    assert payload["status"] == "processing", payload


async def main() -> None:
    await test_polls_until_done()
    await test_gives_up_honestly_after_budget()
    print("ok")


if __name__ == "__main__":
    anyio.run(main)
