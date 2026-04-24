# syntax=docker/dockerfile:1.7

# ---------- builder ----------
FROM python:3.13-slim AS builder

ENV POETRY_VERSION=2.3.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_CREATE=false \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN pip install --no-cache-dir "poetry==${POETRY_VERSION}"

WORKDIR /src
COPY pyproject.toml poetry.lock ./

# Install runtime deps only (exclude dev group), then strip build-time tooling.
RUN poetry install --no-root --only=main \
 && pip uninstall -y \
      poetry poetry-core poetry-plugin-export \
      keyring cleo dulwich \
      SecretStorage jeepney \
      crashtest build installer \
    || true

# ---------- runtime ----------
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Non-root user (uid 1000 to match k8s securityContext)
RUN addgroup --system --gid 1000 app \
 && adduser  --system --uid 1000 --ingroup app --home /app --shell /usr/sbin/nologin app

WORKDIR /app

# Copy site-packages + scripts (uvicorn entry) from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Application code (templates + static + python)
COPY app ./app

USER 1000:1000

EXPOSE 8000

# Respect env for host/port overrides; default to 0.0.0.0:8000
CMD ["sh", "-c", "exec uvicorn app.main:app --host ${HOST:-0.0.0.0} --port ${PORT:-8000}"]
