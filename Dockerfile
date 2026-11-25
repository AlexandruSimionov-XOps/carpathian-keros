# syntax=docker/dockerfile:1
# Carpathian Keros: production image for Docker and Google Cloud Run.
#
#   docker build -t carpathian-keros .
#   docker run --rm -p 8080:8080 carpathian-keros      → http://localhost:8080
#
# Two stages: dependencies are installed into a virtualenv in `build`, and only that venv plus the app files are
# copied into `runtime`. No compilers, pip caches or build tools reach the final image.

ARG PYTHON_VERSION=3.14

# ---------------------------------------------------------------- build: install Python dependencies
FROM python:${PYTHON_VERSION}-slim AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt /tmp/requirements.txt
# pip itself is only needed here: remove it from the venv so it doesn't ship (smaller, fewer scanner findings).
RUN pip install -r /tmp/requirements.txt \
 && pip uninstall -y pip

# ---------------------------------------------------------------- runtime: what actually runs
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG VERSION=dev
LABEL org.opencontainers.image.title="Carpathian Keros" \
      org.opencontainers.image.description="Bilingual (RO/EN) weather dashboard for Romania's 319 official cities" \
      org.opencontainers.image.source="https://github.com/AlexandruSimionov-XOps/carpathian-keros" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

# A Unicode TTF for the PDF reports: without it they fall back to ASCII and lose ă â î ș ț.
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

# Unprivileged user with a fixed UID (no home, no shell). The app files below stay owned by root, so the
# running process can't modify its own code.
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin app

COPY --from=build /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app
# .dockerignore is an allow-list: only app.py, gunicorn.conf.py, pyproject.toml, requirements.txt, services/,
# templates/, static/ and data/ are in the build context.
COPY . .
# Precompile as root, so the read-only app doesn't have to at every cold start (Cloud Run scales from zero).
RUN python -m compileall -q /app

USER app
EXPOSE 8080

# Docker / docker compose use this; Cloud Run uses its own probes (see docs/setup.md).
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --start-interval=2s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT', '8080'), timeout=2)"]

# Exec form: gunicorn is PID 1 and receives SIGTERM directly, so Cloud Run's shutdown is clean.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
