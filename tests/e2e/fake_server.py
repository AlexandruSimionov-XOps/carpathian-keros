"""App server for the browser tests: the real app, with the recorded Open-Meteo forecast injected.

    PORT=8765 python tests/e2e/fake_server.py

Routes, templates, static files and security headers are the production ones. Only the weather source is the
FakeSession from tests/fakes.py (AGENTS.md, Article I-D), so the browser tests don't depend on Open-Meteo being
reachable from a CI runner. The page still loads its CDN scripts for real.
Every city shows the same recorded weather; the tests check behaviour, not forecasts.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:  # when run as a script
    sys.path.insert(0, str(ROOT))

from flask import Flask  # noqa: E402

from app import create_app  # noqa: E402
from services.cities import CityRegistry  # noqa: E402
from services.weather_service import WeatherService  # noqa: E402
from tests.fakes import FakeSession, load_forecast  # noqa: E402


def build_app() -> tuple[Flask, FakeSession]:
    """The production app with a FakeSession as its only route to "Open-Meteo"."""
    session = FakeSession(load_forecast())
    registry = CityRegistry()
    service = WeatherService(session=session, registry=registry)
    return create_app(weather_service=service, registry=registry), session


if __name__ == "__main__":
    app, _ = build_app()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "8765")), threaded=True)
