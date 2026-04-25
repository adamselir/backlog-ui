"""FastAPI app factory for backlog-ui."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.client import PlatformClient
from app.config import Settings
from app.routes import register_routes

log = logging.getLogger("backlog-ui")


def create_app(
    *,
    platform_base_url: str | None = None,
    request_timeout_s: float | None = None,
    cf_access_client_id: str | None = None,
    cf_access_client_secret: str | None = None,
) -> FastAPI:
    overrides: dict = {}
    if platform_base_url is not None:
        overrides["platform_base_url"] = platform_base_url
    if cf_access_client_id is not None:
        overrides["cf_access_client_id"] = cf_access_client_id
    if cf_access_client_secret is not None:
        overrides["cf_access_client_secret"] = cf_access_client_secret
    settings = Settings(**overrides)
    if request_timeout_s is not None:
        settings.request_timeout_s = request_timeout_s

    client = PlatformClient(
        base_url=settings.platform_base_url,
        timeout_s=settings.request_timeout_s,
        cf_access_client_id=settings.cf_access_client_id,
        cf_access_client_secret=settings.cf_access_client_secret,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await client.aclose()

    app = FastAPI(title="Backlog UI", lifespan=lifespan)

    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
    register_routes(app, templates=templates, client=client)
    return app


# Entry point for uvicorn in prod — env-driven
def _maybe_app():
    """Construct module-level app if PLATFORM_BASE_URL is set.

    Allows `import app.main` in tests without requiring env vars; uvicorn in
    prod gets `app.main:app` with the env populated.
    """
    import os

    if os.getenv("PLATFORM_BASE_URL"):
        return create_app()
    return None


app = _maybe_app()
