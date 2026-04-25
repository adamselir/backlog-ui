# backlog-ui

HTMX frontend for the homelab-platform backlog. Deployed at https://backlog.amy-eli.com.

## Architecture

- Python FastAPI + Jinja2 + HTMX
- Server-rendered, no SPA bundle
- Reads from `homelab-platform` REST API at `/api/v1/backlog/*`
- **UI edge auth**: CF Access + cf-access-proxy sidecar validates the user's JWT
- **Cross-app auth**: backlog-ui → homelab-platform uses a CF Access service token
  (`backlog-ui`, scoped to the `automation-backlog-ui` policy on the homelab-platform
  Access app). Browser JWTs are *never* forwarded — each app has an independent
  trust boundary. The user identity flows through as `X-Forwarded-User` for audit
  correlation only.

See `homelab-platform/docs/superpowers/specs/2026-04-24-slice-e-backlog-ui-design.md`
and the implementation plan for details.

## Development

```bash
poetry install
poetry run pytest
poetry run uvicorn app.main:app --reload --port 8000 \
  --env-file .env.local  # set PLATFORM_BASE_URL=...
```
