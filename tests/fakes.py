"""Test doubles shared by the unit/API tests (conftest.py) and the browser tests' app server (e2e/fake_server.py).

Open-Meteo is replaced by `FakeSession`, which serves the recorded response in tests/fixtures/open_meteo_forecast.json.
They're injected through the app's constructors (AGENTS.md, Article I-D), never patched in globally.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import requests

FORECAST_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "open_meteo_forecast.json"


def load_forecast() -> dict:
    """A fresh copy of the recorded Open-Meteo forecast response."""
    return json.loads(FORECAST_FIXTURE.read_text(encoding="utf-8"))


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
