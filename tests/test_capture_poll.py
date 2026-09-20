"""Self-check for the non-blocking capture / capture_status tools. Run directly:
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


async def test_capture_returns_immediately_without_polling() -> None:
    fake = FakeClient(
        [
            {"job_id": "1", "status": "queued"},
            {"job_id": "1", "status": "processing"},
            {"job_id": "1", "status": "done", "episode_ids": ["e1"]},
        ]
    )
    mcp = server_mod.build_server(fake)  # type: ignore[arg-type]
    result = await mcp.call_tool("capture", {"text": "hello"})
    assert not result.is_error, result.content
    payload = json.loads(result.content[0].text)
    assert payload["status"] == "queued", payload  # first status, no polling happened


async def test_capture_status_checks_progress() -> None:
    fake = FakeClient(
        [
            {"job_id": "1", "status": "processing"},
            {"job_id": "1", "status": "done", "episode_ids": ["e1"]},
        ]
    )
    mcp = server_mod.build_server(fake)  # type: ignore[arg-type]
    result = await mcp.call_tool("capture_status", {"job_id": "1"})
    assert not result.is_error, result.content
    payload = json.loads(result.content[0].text)
    assert payload["status"] == "done", payload
    assert payload["episode_ids"] == ["e1"], payload


async def main() -> None:
    await test_capture_returns_immediately_without_polling()
    await test_capture_status_checks_progress()
    print("ok")


if __name__ == "__main__":
    anyio.run(main)
