import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    app = create_app(platform_base_url="http://fake:8000", request_timeout_s=2.0)
    with TestClient(app) as c:
        yield c


def _item(**overrides):
    base = {
        "id": "11111111-1111-1111-1111-111111111111",
        "title": "Hello",
        "priority": "high",
        "module": "security",
        "status": "open",
        "updated_at": "2026-04-24T18:16:35Z",
        "source": "manual",
        "description": None,
        "severity": None,
        "assignee": None,
        "source_ref": None,
        "source_url": None,
        "external_id": None,
        "evidence": None,
        "classification": "internal",
        "first_seen": "2026-04-24T18:16:35Z",
        "last_seen": "2026-04-24T18:16:35Z",
        "metadata": None,
        "created_at": "2026-04-24T18:16:35Z",
    }
    base.update(overrides)
    return base


def test_root_renders_list_skeleton(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<title>Backlog" in r.text
    assert 'id="rows"' in r.text


def test_items_fragment_renders_rows(client):
    with respx.mock(base_url="http://fake:8000") as mock:
        mock.get("/api/v1/backlog/items").respond(
            200,
            json={"items": [_item()], "total": 1, "limit": 100, "offset": 0},
        )
        r = client.get("/items")
        assert r.status_code == 200
        assert "Hello" in r.text
        assert "pri-high" in r.text


def test_items_fragment_renders_empty_state(client):
    with respx.mock(base_url="http://fake:8000") as mock:
        mock.get("/api/v1/backlog/items").respond(
            200, json={"items": [], "total": 0, "limit": 100, "offset": 0}
        )
        r = client.get("/items")
        assert r.status_code == 200
        assert "No items" in r.text


def test_items_fragment_on_5xx_renders_toast(client):
    with respx.mock(base_url="http://fake:8000") as mock:
        mock.get("/api/v1/backlog/items").mock(
            side_effect=[httpx.Response(500), httpx.Response(500)]
        )
        r = client.get("/items")
        assert r.status_code == 200  # UI owns the error envelope
        assert "Could not load" in r.text


def test_patch_status_returns_row_fragment(client):
    with respx.mock(base_url="http://fake:8000") as mock:
        mock.patch("/api/v1/backlog/items/x/status").respond(
            200, json={"item": _item(id="x", status="in_progress")}
        )
        r = client.patch("/items/x/status", data={"status": "in_progress"})
        assert r.status_code == 200
        assert "in_progress" in r.text


def test_counts_fragment_renders_chips(client):
    with respx.mock(base_url="http://fake:8000") as mock:
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
        r = client.get("/items/counts")
        assert r.status_code == 200
        assert "open: 3" in r.text
        assert "done: 2" in r.text


def test_drawer_fragment_renders_item_detail(client):
    with respx.mock(base_url="http://fake:8000") as mock:
        mock.get("/api/v1/backlog/items/x").respond(
            200, json={"item": _item(id="x", description="full detail here")}
        )
        r = client.get("/items/x")
        assert r.status_code == 200
        assert "full detail here" in r.text


def test_drawer_unknown_id_404(client):
    with respx.mock(base_url="http://fake:8000") as mock:
        mock.get("/api/v1/backlog/items/missing").respond(
            404, json={"error": {"code": "not_found"}}
        )
        r = client.get("/items/missing")
        assert r.status_code == 404


def test_healthz_ok(client):
    assert client.get("/healthz").status_code == 200


def test_readyz_ok(client):
    assert client.get("/readyz").status_code == 200


def test_metrics_exposes_prometheus(client):
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "backlog_ui_renders_total" in r.text
