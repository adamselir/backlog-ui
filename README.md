# backlog-ui

HTMX frontend for the homelab-platform backlog. Deployed at https://backlog.amy-eli.com.

## Architecture

- Python FastAPI + Jinja2 + HTMX
- Server-rendered, no SPA bundle
- Reads from `homelab-platform` REST API at `/api/v1/backlog/*`
- Cluster-internal HTTP from UI pod → platform pod (no CF round-trip)
- Edge auth via CF Access + cf-access-proxy sidecar

See `homelab-platform/docs/superpowers/specs/2026-04-24-slice-e-backlog-ui-design.md`
and the implementation plan for details.

## Development

```bash
poetry install
poetry run pytest
poetry run uvicorn app.main:app --reload --port 8000 \
  --env-file .env.local  # set PLATFORM_BASE_URL=...
```
