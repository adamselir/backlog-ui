"""HTTP routes for backlog-ui."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates
from prometheus_client import Counter, Histogram, generate_latest

from app.client import PlatformClient

UI_RENDERS = Counter("backlog_ui_renders_total", "UI fragment renders", ["page"])
UI_API_LATENCY = Histogram(
    "backlog_ui_api_call_duration_seconds",
    "UI → platform API call duration",
    ["op"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
)


def _csv(v: str | None) -> list[str] | None:
    if not v:
        return None
    parts = [p for p in v.split(",") if p]
    return parts or None


def register_routes(app: FastAPI, *, templates: Jinja2Templates, client: PlatformClient) -> None:
    r = APIRouter()

    def _filter_params(request: Request) -> dict:
        q = request.query_params
        return {
            "priority": _csv(q.get("priority")),
            "module": _csv(q.get("module")),
            "status": _csv(q.get("status")),
            "source": _csv(q.get("source")),
            "q": q.get("q"),
            "sort": _csv(q.get("sort")),
        }

    def _jwt_from(request: Request) -> str | None:
        return request.headers.get("Cf-Access-Jwt-Assertion")

    @r.get("/", response_class=HTMLResponse)
    async def root(request: Request):
        UI_RENDERS.labels("list").inc()
        return templates.TemplateResponse(
            "list.html",
            {"request": request, "filters": _filter_params(request)},
        )

    @r.get("/items", response_class=HTMLResponse)
    async def items_fragment(request: Request):
        params = _filter_params(request)
        params_nonnone = {k: v for k, v in params.items() if v is not None}
        try:
            with UI_API_LATENCY.labels("list_items").time():
                data = await client.list_items(jwt=_jwt_from(request), **params_nonnone)
        except httpx.HTTPError:
            return templates.TemplateResponse(
                "fragments/toast.html",
                {
                    "request": request,
                    "message": "Could not load items — retrying on next refresh",
                },
            )
        UI_RENDERS.labels("rows").inc()
        return templates.TemplateResponse(
            "fragments/rows.html",
            {
                "request": request,
                "items": data["items"],
                "total": data["total"],
            },
        )

    @r.get("/items/counts", response_class=HTMLResponse)
    async def counts_fragment(request: Request):
        params = _filter_params(request)
        params_nonnone = {
            k: v
            for k, v in params.items()
            if v is not None and k in {"priority", "module", "status", "source", "q"}
        }
        try:
            with UI_API_LATENCY.labels("counts").time():
                counts = await client.counts(jwt=_jwt_from(request), **params_nonnone)
        except httpx.HTTPError:
            return HTMLResponse('<div class="chips">—</div>')
        UI_RENDERS.labels("counts").inc()
        return templates.TemplateResponse(
            "fragments/counts.html", {"request": request, "counts": counts}
        )

    @r.get("/items/{item_id}", response_class=HTMLResponse)
    async def drawer(request: Request, item_id: str):
        try:
            with UI_API_LATENCY.labels("get_item").time():
                item = await client.get_item(item_id, jwt=_jwt_from(request))
        except httpx.HTTPError:
            raise HTTPException(status_code=502)
        if item is None:
            raise HTTPException(status_code=404)
        UI_RENDERS.labels("drawer").inc()
        return templates.TemplateResponse(
            "fragments/drawer.html", {"request": request, "item": item}
        )

    @r.patch("/items/{item_id}/status", response_class=HTMLResponse)
    async def patch_status(request: Request, item_id: str, status: str = Form(...)):
        try:
            with UI_API_LATENCY.labels("patch_status").time():
                updated = await client.patch_status(item_id, status, jwt=_jwt_from(request))
        except httpx.HTTPStatusError as exc:
            return HTMLResponse(
                f'<tr><td colspan="5">error: {exc.response.status_code}</td></tr>',
                status_code=200,
            )
        except httpx.HTTPError:
            raise HTTPException(status_code=502)
        UI_RENDERS.labels("row_after_patch").inc()
        return templates.TemplateResponse(
            "fragments/row.html", {"request": request, "item": updated}
        )

    @r.get("/healthz")
    async def healthz():
        return JSONResponse({"status": "ok"})

    @r.get("/readyz")
    async def readyz():
        return JSONResponse({"status": "ok"})

    @r.get("/metrics")
    async def metrics():
        return Response(generate_latest(), media_type="text/plain; charset=utf-8")

    app.include_router(r)
