"""httpx client for the homelab-platform REST API."""

from __future__ import annotations

import asyncio

import httpx


class PlatformClient:
    """Async client for /api/v1/backlog/* endpoints.

    Authenticates to homelab-platform with a CF Access service token —
    NOT by forwarding the user's browser JWT. The browser JWT is bound to
    the backlog-ui Access app's audience, so forwarding it would force
    homelab-platform to widen its trust boundary; using a separate
    service token (scoped via the `automation-backlog-ui` policy on the
    homelab-platform Access app) keeps the two apps' trust boundaries
    independent and gives clean rotation/audit per app.

    - GETs retry once on 5xx / RequestError with 500ms backoff.
    - PATCHes never retry.
    - 404 on get_item returns None; every other 4xx/5xx raises.

    The optional `forwarded_user` argument lets routes propagate the
    authenticated browser user identity to homelab-platform via an
    `X-Forwarded-User` header for audit-log correlation. It is informational
    only — homelab-platform's trust still derives from the service token.
    """

    def __init__(
        self,
        *,
        base_url: str,
        timeout_s: float,
        cf_access_client_id: str = "",
        cf_access_client_secret: str = "",
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=httpx.Timeout(timeout_s, connect=timeout_s),
        )
        self._cf_access_client_id = cf_access_client_id
        self._cf_access_client_secret = cf_access_client_secret

    async def aclose(self) -> None:
        await self._client.aclose()

    @staticmethod
    def _csv(values: list[str] | None) -> str | None:
        if not values:
            return None
        return ",".join(values)

    def _auth_headers(self, forwarded_user: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self._cf_access_client_id and self._cf_access_client_secret:
            headers["CF-Access-Client-Id"] = self._cf_access_client_id
            headers["CF-Access-Client-Secret"] = self._cf_access_client_secret
        if forwarded_user:
            headers["X-Forwarded-User"] = forwarded_user
        return headers

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
        forwarded_user: str | None = None,
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
        r = await self._get_with_retry(
            "/api/v1/backlog/items",
            params=params,
            headers=self._auth_headers(forwarded_user),
        )
        r.raise_for_status()
        return r.json()

    async def get_item(self, item_id: str, *, forwarded_user: str | None = None) -> dict | None:
        r = await self._get_with_retry(
            f"/api/v1/backlog/items/{item_id}",
            headers=self._auth_headers(forwarded_user),
        )
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()["item"]

    async def counts(
        self,
        *,
        forwarded_user: str | None = None,
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
        r = await self._get_with_retry(
            "/api/v1/backlog/items/counts",
            params=params,
            headers=self._auth_headers(forwarded_user),
        )
        r.raise_for_status()
        return r.json()

    async def summary(self, *, forwarded_user: str | None = None) -> dict:
        r = await self._get_with_retry(
            "/api/v1/backlog/summary",
            headers=self._auth_headers(forwarded_user),
        )
        r.raise_for_status()
        return r.json()

    async def patch_status(
        self, item_id: str, status: str, *, forwarded_user: str | None = None
    ) -> dict:
        r = await self._client.patch(
            f"/api/v1/backlog/items/{item_id}/status",
            json={"status": status},
            headers=self._auth_headers(forwarded_user),
        )
        r.raise_for_status()
        return r.json()["item"]
