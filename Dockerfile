# syntax=docker/dockerfile:1
# Carpathian Keros: production image for Docker and Google Cloud Run.
#
#   docker build -t carpathian-keros .
#   docker run --rm -p 8080:8080 carpathian-keros      → http://localhost:8080
#
# Two stages: dependencies are installed into a virtualenv in `build`, and only that venv plus the app files are
# copied into `runtime`. No compilers, pip caches or build tools reach the final image.
#
# Base image pinned by digest (both stages): a tag can be re-pointed, a digest can't. Dependabot opens PRs to bump it.

# ---------------------------------------------------------------- build: install Python dependencies
FROM python:3.14-slim@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b AS build

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY requirements.txt /tmp/requirements.txt
# pip itself is only needed here: remove it from the venv so it doesn't ship (smaller, fewer scanner findings).
RUN pip install -r /tmp/requirements.txt \
 && pip uninstall -y pip

# ---------------------------------------------------------------- runtime: what actually runs
FROM python:3.14-slim@sha256:22eafb370920ad8b429e0aec3fff433e0669968519f5d60469d83729c138b28b AS runtime

ARG VERSION=dev
LABEL org.opencontainers.image.title="Carpathian Keros" \
      org.opencontainers.image.description="Bilingual (RO/EN) weather dashboard for Romania's 319 official cities" \
      org.opencontainers.image.source="https://github.com/AlexandruSimionov-XOps/carpathian-keros" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${VERSION}"

# - fonts-dejavu-core: a Unicode TTF for the PDF reports (without it they fall back to ASCII and lose ă â î ș ț).
# - upgrade: Debian security fixes that landed after the base image was built (Trivy fails CI on fixable HIGH/CRITICAL).
# - The interpreter's own pip and ensurepip's bundled wheels go: the app runs from /opt/venv and never installs
#   anything, but they vendor urllib3, msgpack and setuptools, which had HIGH CVEs flagged by Trivy.
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/* \
 && python -m pip uninstall -y pip \
 && rm -f /usr/local/lib/python3.*/ensurepip/_bundled/*.whl

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

# Numeric, so platforms can verify "not root" without resolving names (hadolint DL3066).
USER 10001:10001
EXPOSE 8080

# Docker / docker compose use this; Cloud Run uses its own probes (see docs/setup.md).
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --start-interval=2s --retries=3 \
  CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT', '8080'), timeout=2)"]

# Exec form: gunicorn is PID 1 and receives SIGTERM directly, so Cloud Run's shutdown is clean.
CMD ["gunicorn", "-c", "gunicorn.conf.py", "app:app"]
