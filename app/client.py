"""httpx client for the homelab-platform REST API."""

from __future__ import annotations

import asyncio

import httpx


class PlatformClient:
    """Async client for /api/v1/backlog/* endpoints.

    - GETs retry once on 5xx / RequestError with 500ms backoff.
    - PATCHes never retry.
    - 404 on get_item returns None; every other 4xx/5xx raises.
    """

    def __init__(self, *, base_url: str, timeout_s: float) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_s, connect=timeout_s),
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _csv(values: list[str] | None) -> str | None:
        if not values:
            return None
        return ",".join(values)

    @staticmethod
    def _auth_headers(jwt: str | None) -> dict[str, str] | None:
        if not jwt:
            return None
        return {"Cf-Access-Jwt-Assertion": jwt}

    async def _get_with_retry(self, path: str, **kw) -> httpx.Response:
        last_exc: Exception | None = None
        response: httpx.Response | None = None
        for attempt in range(2):
            try:
                response = await self._client.get(path, **kw)
                if response.status_code < 500:
                    return response
            except httpx.RequestError as exc:
                last_exc = exc
            if attempt == 0:
                await asyncio.sleep(0.5)
        if response is not None:
            return response
        assert last_exc is not None
        raise last_exc

    async def list_items(
        self,
        *,
        jwt: str | None = None,
        priority: list[str] | None = None,
        module: list[str] | None = None,
        status: list[str] | None = None,
        source: list[str] | None = None,
        q: str | None = None,
        sort: list[str] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        params: dict[str, str | int] = {"limit": limit, "offset": offset}
        for k, v in (
            ("priority", self._csv(priority)),
            ("module", self._csv(module)),
            ("status", self._csv(status)),
            ("source", self._csv(source)),
            ("q", q),
            ("sort", self._csv(sort)),
        ):
            if v is not None:
                params[k] = v
        kw: dict = {"params": params}
        headers = self._auth_headers(jwt)
        if headers is not None:
            kw["headers"] = headers
        r = await self._get_with_retry("/api/v1/backlog/items", **kw)
        r.raise_for_status()
        return r.json()

    async def get_item(self, item_id: str, *, jwt: str | None = None) -> dict | None:
        kw: dict = {}
        headers = self._auth_headers(jwt)
        if headers is not None:
            kw["headers"] = headers
        r = await self._get_with_retry(f"/api/v1/backlog/items/{item_id}", **kw)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()["item"]

    async def counts(
        self,
        *,
        jwt: str | None = None,
        priority: list[str] | None = None,
        module: list[str] | None = None,
        status: list[str] | None = None,
        source: list[str] | None = None,
        q: str | None = None,
    ) -> dict:
        params: dict[str, str] = {}
        for k, v in (
            ("priority", self._csv(priority)),
            ("module", self._csv(module)),
            ("status", self._csv(status)),
            ("source", self._csv(source)),
            ("q", q),
        ):
            if v is not None:
                params[k] = v
        kw: dict = {"params": params}
        headers = self._auth_headers(jwt)
        if headers is not None:
            kw["headers"] = headers
        r = await self._get_with_retry("/api/v1/backlog/items/counts", **kw)
        r.raise_for_status()
        return r.json()

    async def summary(self, *, jwt: str | None = None) -> dict:
        kw: dict = {}
        headers = self._auth_headers(jwt)
        if headers is not None:
            kw["headers"] = headers
        r = await self._get_with_retry("/api/v1/backlog/summary", **kw)
        r.raise_for_status()
        return r.json()

    async def patch_status(self, item_id: str, status: str, *, jwt: str | None = None) -> dict:
        headers = self._auth_headers(jwt)
        r = await self._client.patch(
            f"/api/v1/backlog/items/{item_id}/status",
            json={"status": status},
            headers=headers,
        )
        r.raise_for_status()
        return r.json()["item"]
