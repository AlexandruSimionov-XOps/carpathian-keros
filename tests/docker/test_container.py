"""Container tests: build the production image, run it, and check it behaves like Cloud Run will run it.

Opt-in (needs Docker and network access to Open-Meteo):

    CK_DOCKER=1 pytest -m docker
    CK_DOCKER=1 CK_IMAGE=carpathian-keros:ci pytest -m docker   # test an image built elsewhere (e.g. in CI)
"""

from __future__ import annotations

import io
import json
import os
import shutil
import socket
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(os.environ.get("CK_DOCKER") != "1", reason="set CK_DOCKER=1 to run container tests"),
    pytest.mark.skipif(shutil.which("docker") is None, reason="docker CLI not installed"),
]
MAX_IMAGE_BYTES = 300 * 1024 * 1024


def docker(*args: str, check: bool = True, timeout: int = 600) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True, text=True, timeout=timeout, check=check)  # noqa: S603, S607


@pytest.fixture(scope="module")
def image() -> str:
    tag = os.environ.get("CK_IMAGE")
    if tag:
        return tag
    tag = "carpathian-keros:test"
    docker("build", "--pull", "-t", tag, str(ROOT))
    return tag


@pytest.fixture(scope="module")
def container(image):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    # Cloud Run sets PORT itself; we pass a non-default one to prove the image honours it.
    cid = docker("run", "-d", "--rm", "-e", "PORT=9090", "-p", f"127.0.0.1:{port}:9090", image).stdout.strip()
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(f"{url}/health", timeout=2)  # noqa: S310 - local container
                break
            except OSError:
                time.sleep(0.5)
        else:
            pytest.fail("container never became ready:\n" + docker("logs", cid, check=False).stdout)
        yield {"id": cid, "url": url}
    finally:
        docker("rm", "-f", cid, check=False)


def get(url: str):
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - local container
        return resp.status, dict(resp.headers), resp.read()


def test_health_and_version(container):
    status, headers, body = get(container["url"] + "/health")
    assert status == 200
    assert json.loads(body)["status"] == "ok"
    assert headers["X-Content-Type-Options"] == "nosniff"


def test_dashboard_and_weather_api(container):
    status, _, html = get(container["url"] + "/")
    assert status == 200 and b"Carpathian Keros" in html
    status, _, body = get(container["url"] + "/api/weather?city=Iasi")
    assert status == 200 and json.loads(body)["location"]["name"] == "Iași"


def test_pdf_keeps_romanian_diacritics(container):
    """The image must ship a Unicode font; without it the PDF falls back to ASCII ('Brasov')."""
    from pypdf import PdfReader

    status, headers, body = get(container["url"] + "/api/report/export?city=Bra%C8%99ov&lang=ro")
    assert status == 200 and headers["Content-Type"] == "application/pdf"
    text = PdfReader(io.BytesIO(body)).pages[0].extract_text()
    assert "Brașov" in text and "Condiții actuale" in text


def test_starts_without_errors_in_the_logs(container):
    """Regression: gunicorn 27 logged 'Control server error: Permission denied: /nonexistent' on every start."""
    logs = docker("logs", container["id"]).stdout + docker("logs", container["id"]).stderr
    assert "[ERROR]" not in logs and "Traceback" not in logs, logs


def test_runs_as_a_non_root_user(container):
    uid = docker("exec", container["id"], "id", "-u").stdout.strip()
    assert uid != "0"


def test_image_contains_only_what_the_app_needs(image):
    listing = set(docker("run", "--rm", "--entrypoint", "ls", image, "-A", "/app").stdout.split())
    assert {"app.py", "services", "templates", "static", "data", "gunicorn.conf.py"} <= listing
    assert not listing & {"tests", ".git", "docs", "assets", ".venv", "scripts", ".env"}


def test_app_venv_has_no_package_installer(image):
    """pip is only needed while building; at runtime it's dead weight (14 MB) and a frequent scanner finding."""
    result = docker("run", "--rm", "--entrypoint", "/opt/venv/bin/python", image, "-c", "import pip", check=False)
    assert result.returncode != 0


def test_image_has_no_package_installer_at_all(image):
    """The base image's own pip vendors urllib3/msgpack and ships setuptools wheels: Trivy flagged HIGH CVEs there,
    in tools the app never runs. Regression for that finding: neither pip nor ensurepip's bundled wheels remain."""
    script = (
        "import importlib.util, pathlib, sysconfig; "
        "bundled = pathlib.Path(sysconfig.get_paths()['stdlib']) / 'ensurepip' / '_bundled'; "
        "print(importlib.util.find_spec('pip') is None, not any(bundled.glob('*.whl')))"
    )
    out = docker("run", "--rm", "--entrypoint", "/usr/local/bin/python3", image, "-c", script).stdout.split()
    assert out == ["True", "True"]


def test_image_size_stays_small(image):
    size = int(docker("image", "inspect", "-f", "{{.Size}}", image).stdout)
    assert size < MAX_IMAGE_BYTES, f"{size / 1e6:.0f} MB"


def test_docker_healthcheck_reports_healthy(container):
    for _ in range(40):
        state = docker("inspect", "-f", "{{.State.Health.Status}}", container["id"]).stdout.strip()
        if state == "healthy":
            return
        time.sleep(1)
    pytest.fail(f"health status stayed {state!r}")


def test_stops_quickly_and_cleanly_on_sigterm(image):
    """Cloud Run sends SIGTERM and waits 10 s before killing. gunicorn must be PID 1 (exec form) to receive it."""
    cid = docker("run", "-d", image).stdout.strip()
    try:
        time.sleep(3)
        started = time.monotonic()
        docker("stop", "-t", "10", cid)
        assert time.monotonic() - started < 8
        assert docker("inspect", "-f", "{{.State.ExitCode}}", cid).stdout.strip() == "0"
    finally:
        docker("rm", "-f", cid, check=False)
