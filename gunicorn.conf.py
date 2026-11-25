"""gunicorn settings for the production image (Docker / Google Cloud Run).

Locally you still use `python app.py`. In the container: `gunicorn -c gunicorn.conf.py app:app`.
Environment:
    PORT              port to listen on; Cloud Run sets it (default 8080)
    WEB_CONCURRENCY   worker processes (default 2; Cloud Run's free tier gives 1 vCPU)
    GUNICORN_THREADS  threads per worker (default 4; requests mostly wait on Open-Meteo, so threads are cheap)
"""

from __future__ import annotations

import os


def _positive_int(name: str, default: int) -> int:
    raw = os.environ.get(name, str(default))
    value = int(raw)  # raises ValueError for non-numbers
    if value < 1:
        raise ValueError(f"{name} must be >= 1, got {raw!r}")
    return value


# Cloud Run routes traffic to the container's port. Bind every interface: the request comes from outside it.
bind = f"0.0.0.0:{_positive_int('PORT', 8080)}"

workers = _positive_int("WEB_CONCURRENCY", 2)
threads = _positive_int("GUNICORN_THREADS", 4)  # >1 selects the gthread worker

# A weather call can take up to 3 attempts x (3.05 s connect + 8 s read) plus backoff (≈35 s): don't kill it first.
timeout = 60
# Cloud Run sends SIGTERM and kills the container 10 s later: finish in-flight requests well before that.
graceful_timeout = 8
keepalive = 5

# gunicorn 27's control socket (for the `gunicornc` admin CLI) lives in $HOME, and the container user has none.
# The platform manages the process, so it isn't needed.
control_socket_disable = True

# Logs to stdout/stderr, where Docker and Cloud Logging collect them.
accesslog = "-"
errorlog = "-"
loglevel = "info"

# The app is stateless apart from a per-process cache; recycle workers now and then to bound memory growth.
max_requests = 2000
max_requests_jitter = 200
