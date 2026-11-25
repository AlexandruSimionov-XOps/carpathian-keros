"""The browser tests' app server serves recorded weather and never calls Open-Meteo (runs offline, not opt-in).

Regression: browser tests used the live Open-Meteo API. When GitHub's runner couldn't get an answer in time, every
test timed out on "Se încarcă vremea…" (23 errors, 6 minutes), though the code was fine.
"""

from __future__ import annotations

import re
from pathlib import Path

from services.weather_service import FORECAST_URL
from tests.e2e.fake_server import build_app
from tests.fakes import FakeSession, load_forecast

ROOT = Path(__file__).resolve().parents[2]


def test_serves_the_recorded_forecast():
    app, _ = build_app()
    resp = app.test_client().get("/api/weather", query_string={"city": "Iasi"})
    assert resp.status_code == 200
    assert resp.json["location"]["name"] == "Iași"
    assert resp.json["current"]["temperature"] == load_forecast()["current"]["temperature_2m"]


def test_weather_requests_go_to_the_fake_never_the_network():
    app, session = build_app()
    app.test_client().get("/api/weather", query_string={"city": "Oradea"})
    assert isinstance(session, FakeSession)
    assert [url for url, _ in session.calls] == [FORECAST_URL]


def test_the_rest_of_the_app_is_real():
    """Only the weather source is faked: routes, templates and security headers are the production ones."""
    app, _ = build_app()
    client = app.test_client()
    page = client.get("/")
    assert page.status_code == 200 and b"Carpathian Keros" in page.data
    assert "default-src 'self'" in page.headers["Content-Security-Policy"]
    assert client.get("/api/cities").json["count"] == 319
    assert client.get("/api/report/export", query_string={"city": "Iasi"}).data[:5] == b"%PDF-"


def test_browser_tests_start_the_fake_server_not_the_production_entry_point():
    source = (ROOT / "tests/e2e/test_ui.py").read_text(encoding="utf-8")
    assert re.search(r'"tests/e2e/fake_server\.py"', source)
    assert '"app.py"' not in source
