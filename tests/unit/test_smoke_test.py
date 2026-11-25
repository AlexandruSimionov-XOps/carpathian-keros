"""scripts/smoke_test.py: the post-deploy check, run against a real HTTP server (the app with recorded weather)."""

from __future__ import annotations

import socket
import subprocess
import sys
import threading
from pathlib import Path
from wsgiref.simple_server import WSGIRequestHandler, make_server

import pytest

from scripts.smoke_test import SmokeTestError, run_checks
from tests.e2e.fake_server import build_app


class _QuietHandler(WSGIRequestHandler):
    def log_message(self, *args) -> None:
        pass


@pytest.fixture(scope="module")
def server_url():
    app, _ = build_app()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd = make_server("127.0.0.1", port, app, handler_class=_QuietHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    httpd.shutdown()


def test_passes_against_a_healthy_app_with_the_expected_version(server_url):
    from app import APP_VERSION

    results = run_checks(server_url, APP_VERSION, attempts=1)
    assert [name for name, _ in results] == ["health", "dashboard", "weather", "pdf"]


def test_fails_when_a_different_version_is_live(server_url):
    """Catches a deploy that didn't actually roll out (old revision still answering)."""
    with pytest.raises(SmokeTestError, match="version"):
        run_checks(server_url, "0.0.0-not-deployed", attempts=1)


def test_still_fails_under_python_optimize_mode(server_url):
    """Regression: the checks were `assert` statements, which `python -O` removes, so every check "passed"."""
    script = Path(__file__).resolve().parents[2] / "scripts/smoke_test.py"
    result = subprocess.run(  # noqa: S603 - fixed argv
        [sys.executable, "-O", str(script), server_url, "0.0.0-not-deployed"],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 1, result.stdout + result.stderr
    assert "version" in result.stdout


def test_fails_when_nothing_answers():
    with pytest.raises(SmokeTestError):
        run_checks("http://127.0.0.1:9", "1.0.0", attempts=1, timeout=1)
