from __future__ import annotations

import httpx

_TIMEOUT = 60.0


class CebClient:
    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "CF-Access-Client-Id": client_id,
                "CF-Access-Client-Secret": client_secret,
            },
            timeout=_TIMEOUT,
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    @staticmethod
    async def _check(response: httpx.Response) -> dict:
        if response.is_error:
            try:
                detail = response.json().get("detail", response.text)
            except ValueError:
                detail = response.text
            raise RuntimeError(f"{response.status_code}: {detail}")
        return response.json()

    async def health(self) -> dict:
        return await self._check(await self._http.get("/health"))

    async def me(self) -> dict:
        return await self._check(await self._http.get("/v1/me"))

    async def retrieve(self, query: str, k: int = 8) -> dict:
        return await self._check(
            await self._http.post("/v1/retrieve", json={"query": query, "k": k})
        )

    async def answer(self, question: str, k: int = 8) -> dict:
        return await self._check(
            await self._http.post("/v1/answer", json={"question": question, "k": k})
        )

    async def list_episodes(self, offset: int = 0, limit: int = 100) -> dict:
        return await self._check(
            await self._http.get("/v1/episodes", params={"offset": offset, "limit": limit})
        )

    async def get_episode(self, episode_id: str) -> dict:
        return await self._check(await self._http.get(f"/v1/episodes/{episode_id}"))

    async def capture_start(self, text: str, media: list[str] | None = None) -> dict:
        return await self._check(
            await self._http.post("/v1/capture", json={"text": text, "media": media})
        )

    async def capture_status(self, job_id: str) -> dict:
        return await self._check(await self._http.get(f"/v1/capture/{job_id}"))
