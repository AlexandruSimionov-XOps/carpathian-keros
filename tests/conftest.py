"""Shared fixtures. Nothing here touches the network (AGENTS.md, Article III.3).

Open-Meteo is replaced by `FakeSession`, which serves a recorded response from
tests/fixtures/open_meteo_forecast.json. Collaborators are injected (Article I-D), never patched globally.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from services.cities import CityRegistry  # noqa: E402
from services.weather_service import TTLCache, WeatherService  # noqa: E402

_FORECAST = json.loads((FIXTURES / "open_meteo_forecast.json").read_text(encoding="utf-8"))


class FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self) -> dict:
        return copy.deepcopy(self._payload)


class FakeSession:
    """Stands in for requests.Session. Set `.error` to make every call raise, or `.payload` to change data."""

    def __init__(self, payload: dict):
        self.payload = payload
        self.error: Exception | None = None
        self.status_code = 200
        self.calls: list[tuple[str, dict]] = []

    def get(self, url: str, params: dict | None = None, timeout=None) -> FakeResponse:
        self.calls.append((url, dict(params or {})))
        if self.error is not None:
            raise self.error
        return FakeResponse(self.payload, self.status_code)


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def forecast_payload() -> dict:
    return copy.deepcopy(_FORECAST)


@pytest.fixture
def fake_session(forecast_payload) -> FakeSession:
    return FakeSession(forecast_payload)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture(scope="session")
def registry() -> CityRegistry:
    return CityRegistry()


@pytest.fixture
def service(fake_session, registry, clock) -> WeatherService:
    return WeatherService(session=fake_session, registry=registry, cache=TTLCache(600, clock=clock))


@pytest.fixture
def app(service, registry):
    flask_app = create_app(weather_service=service, registry=registry)
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()
