# syntax=docker/dockerfile:1.7

# ---------- builder ----------
FROM python:3.13-slim AS builder

ENV POETRY_VERSION=2.3.3 \
    POETRY_HOME=/opt/poetry \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /app
COPY pyproject.toml poetry.lock ./

# Install runtime deps only (exclude dev group) into an in-project venv. Only the
# app's runtime deps land in /app/.venv; the Poetry toolchain (poetry/dulwich/
# cleo/…) is never copied into the runtime image.
RUN poetry config virtualenvs.in-project true \
 && poetry install --no-interaction --no-ansi --only main --no-root

# ---------- runtime ----------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# python:3.13-slim lags Debian security updates: the 2026-10-01 base still ships
# libpcre2-8-0 10.46-1~deb13u2 (CVE-2026-103111, HIGH; fixed in deb13u3 on
# trixie-security). Patch just that package in-image rather than allowlisting
# it. Drop this once the upstream base ships deb13u3.
RUN apt-get update \
    && apt-get install -y --only-upgrade --no-install-recommends libpcre2-8-0 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (uid 1000 to match k8s securityContext)
RUN addgroup --system --gid 1000 app \
 && adduser  --system --uid 1000 --ingroup app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

# Copy only the app's runtime venv from the builder (no Poetry toolchain).
COPY --from=builder /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# Application code (templates + static + python)
COPY app ./app

USER 1000:1000

EXPOSE 8000

# Respect env for host/port overrides; default to 0.0.0.0:8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
