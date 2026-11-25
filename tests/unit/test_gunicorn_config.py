"""gunicorn.conf.py: the production server settings used by the Docker image (and Cloud Run)."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from services.weather_service import REQUEST_TIMEOUT

CONFIG = Path(__file__).resolve().parents[2] / "gunicorn.conf.py"


def load(monkeypatch, **env) -> dict:
    for name in ("PORT", "WEB_CONCURRENCY", "GUNICORN_THREADS"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return runpy.run_path(str(CONFIG))


def test_listens_on_all_interfaces_port_8080_by_default(monkeypatch):
    assert load(monkeypatch)["bind"] == "0.0.0.0:8080"


def test_honours_the_port_cloud_run_injects(monkeypatch):
    assert load(monkeypatch, PORT="9123")["bind"] == "0.0.0.0:9123"


def test_worker_and_thread_counts_are_configurable(monkeypatch):
    cfg = load(monkeypatch, WEB_CONCURRENCY="3", GUNICORN_THREADS="2")
    assert (cfg["workers"], cfg["threads"]) == (3, 2)


@pytest.mark.parametrize("bad", ["0", "-1", "abc"])
def test_rejects_nonsense_worker_counts(monkeypatch, bad):
    with pytest.raises(ValueError):
        load(monkeypatch, WEB_CONCURRENCY=bad)


def test_timeout_outlasts_the_worst_case_upstream_call(monkeypatch):
    """Weather calls retry twice (3 attempts) with a connect+read timeout each; gunicorn must not kill them first."""
    worst_case = 3 * sum(REQUEST_TIMEOUT) + 2  # + retry backoff
    assert load(monkeypatch)["timeout"] > worst_case


def test_control_socket_is_disabled(monkeypatch):
    """gunicorn 27's control server wants $HOME/.gunicorn; the container user has no home (logged an error)."""
    assert load(monkeypatch)["control_socket_disable"] is True


def test_logs_go_to_stdout_for_the_platform_to_collect(monkeypatch):
    cfg = load(monkeypatch)
    assert cfg["accesslog"] == "-" and cfg["errorlog"] == "-"
