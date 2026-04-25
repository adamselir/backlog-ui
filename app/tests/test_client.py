import httpx
import pytest
import respx

from app.client import PlatformClient


@pytest.mark.asyncio
async def test_list_items_ok():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/items").respond(
            200,
            json={
                "items": [{"id": "x", "title": "t"}],
                "total": 1,
                "limit": 100,
                "offset": 0,
            },
        )
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            data = await c.list_items(priority=["high"], limit=25)
            assert data["items"][0]["title"] == "t"
            sent = mock.calls.last.request
            assert "priority=high" in str(sent.url)
            assert "limit=25" in str(sent.url)
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_list_items_combines_csv_params():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/items").respond(
            200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
        )
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            await c.list_items(priority=["critical", "high"], status=["open"])
            sent_url = str(mock.calls.last.request.url)
            assert "priority=critical%2Chigh" in sent_url or "priority=critical,high" in sent_url
            assert "status=open" in sent_url
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_get_item_not_found_returns_none():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/items/abc").respond(404, json={"error": {"code": "not_found"}})
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            assert await c.get_item("abc") is None
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_get_item_ok_returns_item():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/items/abc").respond(
            200, json={"item": {"id": "abc", "title": "hi"}}
        )
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            item = await c.get_item("abc")
            assert item == {"id": "abc", "title": "hi"}
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_counts_respects_filters():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/items/counts").respond(
            200,
            json={
                "open": 3,
                "in_progress": 0,
                "done": 2,
                "deferred": 0,
                "wontfix": 0,
                "total": 5,
            },
        )
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            data = await c.counts(priority=["high"])
            assert data["total"] == 5
            assert "priority=high" in str(mock.calls.last.request.url)
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_summary_shape():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/summary").respond(
            200,
            json={
                "total_open": 133,
                "by_priority": {"critical": 0, "high": 5, "medium": 128, "low": 0},
                "by_module": {
                    "security": 40,
                    "feature": 50,
                    "infra": 30,
                    "compliance": 0,
                    "cost": 0,
                    "dx": 13,
                },
                "top_3": [{"id": "x", "title": "t", "priority": "high", "module": "security"}],
            },
        )
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            data = await c.summary()
            assert data["total_open"] == 133
            assert data["by_priority"]["high"] == 5
            assert len(data["top_3"]) == 1
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_patch_status_returns_item():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.patch("/api/v1/backlog/items/x/status").respond(
            200, json={"item": {"id": "x", "status": "done"}}
        )
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            item = await c.patch_status("x", "done")
            assert item["status"] == "done"
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_patch_status_propagates_409():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.patch("/api/v1/backlog/items/x/status").respond(
            409, json={"error": {"code": "bad_transition"}}
        )
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            with pytest.raises(httpx.HTTPStatusError) as ei:
                await c.patch_status("x", "in_progress")
            assert ei.value.response.status_code == 409
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_list_items_retries_once_on_5xx():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        route = mock.get("/api/v1/backlog/items")
        route.side_effect = [
            httpx.Response(500),
            httpx.Response(200, json={"items": [], "total": 0, "limit": 100, "offset": 0}),
        ]
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            data = await c.list_items()
            assert data["total"] == 0
            assert route.call_count == 2
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_patch_status_does_not_retry_on_5xx():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        route = mock.patch("/api/v1/backlog/items/x/status").respond(500)
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            with pytest.raises(httpx.HTTPStatusError):
                await c.patch_status("x", "done")
            assert route.call_count == 1  # no retry
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_list_items_sends_service_token_headers():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/items").respond(
            200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
        )
        c = PlatformClient(
            base_url=base,
            timeout_s=2,
            cf_access_client_id="cid.access",
            cf_access_client_secret="csec",
        )
        try:
            await c.list_items()
            sent = mock.calls.last.request
            assert sent.headers.get("CF-Access-Client-Id") == "cid.access"
            assert sent.headers.get("CF-Access-Client-Secret") == "csec"
            # Browser JWT is NEVER forwarded — that's the whole point of using a
            # service token for cross-app calls.
            assert "Cf-Access-Jwt-Assertion" not in sent.headers
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_patch_status_sends_service_token_headers():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.patch("/api/v1/backlog/items/x/status").respond(
            200, json={"item": {"id": "x", "status": "done"}}
        )
        c = PlatformClient(
            base_url=base,
            timeout_s=2,
            cf_access_client_id="cid.access",
            cf_access_client_secret="csec",
        )
        try:
            await c.patch_status("x", "done")
            sent = mock.calls.last.request
            assert sent.headers.get("CF-Access-Client-Id") == "cid.access"
            assert sent.headers.get("CF-Access-Client-Secret") == "csec"
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_no_credentials_no_auth_headers():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/items").respond(
            200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
        )
        c = PlatformClient(base_url=base, timeout_s=2)
        try:
            await c.list_items()
            sent = mock.calls.last.request
            assert "CF-Access-Client-Id" not in sent.headers
            assert "CF-Access-Client-Secret" not in sent.headers
            assert "Cf-Access-Jwt-Assertion" not in sent.headers
        finally:
            await c.aclose()


@pytest.mark.asyncio
async def test_forwarded_user_header_propagated():
    base = "http://fake:8000"
    async with respx.mock(base_url=base) as mock:
        mock.get("/api/v1/backlog/items").respond(
            200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
        )
        c = PlatformClient(
            base_url=base,
            timeout_s=2,
            cf_access_client_id="cid.access",
            cf_access_client_secret="csec",
        )
        try:
            await c.list_items(forwarded_user="eli@amy-eli.com")
            sent = mock.calls.last.request
            assert sent.headers.get("X-Forwarded-User") == "eli@amy-eli.com"
        finally:
            await c.aclose()
