"""Shared fixtures. Nothing here touches the network (AGENTS.md, Article III.3).

Open-Meteo is replaced by `FakeSession` (tests/fakes.py), which serves a recorded response from
tests/fixtures/open_meteo_forecast.json. Collaborators are injected (Article I-D), never patched globally.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import create_app  # noqa: E402
from services.cities import CityRegistry  # noqa: E402
from services.weather_service import TTLCache, WeatherService  # noqa: E402
from tests.fakes import FakeClock, FakeSession, load_forecast  # noqa: E402


@pytest.fixture
def forecast_payload() -> dict:
    return load_forecast()


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
