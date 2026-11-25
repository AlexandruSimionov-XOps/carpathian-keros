"""Open-Meteo forecast client for Romania's official cities (see services/cities.py).

City names are resolved against the bundled city registry, never by live geocoding, so
only the 319 cities and towns on the official list can be queried.

Responses are kept in a small in-memory TTL cache. If the upstream API fails and an
expired entry is still around, that stale entry is served instead of an error.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cities import MAX_QUERY_LENGTH, CityRegistry, city_registry

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEZONE = "Europe/Bucharest"
CACHE_TTL_SECONDS = 600
REQUEST_TIMEOUT = (3.05, 8)  # (connect, read) seconds


class WeatherServiceError(Exception):
    """Base error; `code` is a stable identifier the frontend translates."""

    code = "upstream_error"
    status = 502


class InvalidCityError(WeatherServiceError):
    code = "invalid_city"
    status = 400


class CityNotFoundError(WeatherServiceError):
    code = "city_not_found"
    status = 404


class UpstreamError(WeatherServiceError):
    code = "upstream_error"
    status = 502


class TTLCache:
    """Thread-safe TTL cache with a size bound. Expired entries stay available as stale."""

    def __init__(self, ttl: float, max_entries: int = 256, clock: Callable[[], float] = time.monotonic):
        self.ttl = ttl
        self.max_entries = max_entries
        self._clock = clock  # injectable so tests can expire entries without sleeping
        self._data: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: Any) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            if entry and self._clock() - entry[0] < self.ttl:
                return entry[1]
            return None

    def get_stale(self, key: Any) -> Any | None:
        with self._lock:
            entry = self._data.get(key)
            return entry[1] if entry else None

    def set(self, key: Any, value: Any) -> None:
        with self._lock:
            self._data[key] = (self._clock(), value)
            self._data.move_to_end(key)
            while len(self._data) > self.max_entries:
                self._data.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._data.clear()


def _build_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(
        total=2,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers["User-Agent"] = "CarpathianKeros/1.0"
    return session


class HttpSession(Protocol):
    """The slice of requests.Session this service uses, so tests can inject a fake (AGENTS.md, Article I-D)."""

    def get(self, url: str, *, params: dict[str, Any] | None = ..., timeout: Any = ...) -> Any: ...


class WeatherService:
    """Collaborators are injectable. The defaults are the production wiring."""

    def __init__(
        self,
        ttl: float = CACHE_TTL_SECONDS,
        *,
        session: HttpSession | None = None,
        registry: CityRegistry | None = None,
        cache: TTLCache | None = None,
    ):
        self._session = session if session is not None else _build_session()
        self._registry = registry if registry is not None else city_registry
        self._forecast_cache = cache if cache is not None else TTLCache(ttl)

    # ---- HTTP ---------------------------------------------------------------
    def _get_json(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = self._session.get(url, params=params, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except requests.Timeout as exc:
            raise UpstreamError("Weather provider timed out") from exc
        except (requests.RequestException, ValueError) as exc:
            raise UpstreamError(f"Weather provider request failed: {exc}") from exc
        if isinstance(data, dict) and data.get("error"):
            raise UpstreamError(data.get("reason", "Weather provider returned an error"))
        return data

    # ---- City lookup ----------------------------------------------------------
    def resolve_city(self, city: str) -> dict[str, Any]:
        city = (city or "").strip()
        if not city or len(city) > MAX_QUERY_LENGTH:
            raise InvalidCityError("City name is missing or too long")
        match = self._registry.resolve(city)
        if match is None:
            raise CityNotFoundError(f"'{city}' is not on the list of Romanian cities")
        return match.location()

    # ---- Forecast -------------------------------------------------------------
    def _fetch_forecast(self, lat: float, lon: float) -> tuple[dict[str, Any], bool]:
        key = (round(lat, 3), round(lon, 3))
        if (cached := self._forecast_cache.get(key)) is not None:
            return cached, False

        params = {
            "latitude": lat,
            "longitude": lon,
            "timezone": TIMEZONE,
            "forecast_days": 7,
            "wind_speed_unit": "kmh",
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,wind_speed_10m,weather_code,is_day",
            "hourly": "temperature_2m,precipitation,precipitation_probability,weather_code",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max,precipitation_sum",
        }
        try:
            raw = self._get_json(FORECAST_URL, params)
            payload = self._shape_forecast(raw)
        except UpstreamError:
            if (stale := self._forecast_cache.get_stale(key)) is not None:
                return stale, True
            raise
        except (KeyError, TypeError, IndexError) as exc:
            raise UpstreamError(f"Unexpected forecast payload: {exc}") from exc

        self._forecast_cache.set(key, payload)
        return payload, False

    @staticmethod
    def _shape_forecast(raw: dict[str, Any]) -> dict[str, Any]:
        cur = raw["current"]
        current = {
            "time": cur["time"],
            "temperature": cur["temperature_2m"],
            "feels_like": cur["apparent_temperature"],
            "humidity": cur["relative_humidity_2m"],
            "wind_speed": cur["wind_speed_10m"],
            "weather_code": cur["weather_code"],
            "is_day": bool(cur.get("is_day", 1)),
        }

        h = raw["hourly"]
        all_hours = [
            {
                "time": h["time"][i],
                "temperature": h["temperature_2m"][i],
                "precipitation": h["precipitation"][i],
                "precipitation_probability": h["precipitation_probability"][i],
                "weather_code": h["weather_code"][i],
            }
            for i in range(len(h["time"]))
        ]
        # Next 24 hours starting at the current local hour.
        current_hour = cur["time"][:13] + ":00"
        start = next((i for i, row in enumerate(all_hours) if row["time"] >= current_hour), 0)
        hourly = all_hours[start : start + 24]
        # Each local day's own hours (00:00–23:00), for the "click a day" view. Times are local, so a date prefix works.
        hours_by_date: dict[str, list[dict[str, Any]]] = {}
        for row in all_hours:
            hours_by_date.setdefault(row["time"][:10], []).append(row)

        d = raw["daily"]
        daily = [
            {
                "date": d["time"][i],
                "weather_code": d["weather_code"][i],
                "temp_max": d["temperature_2m_max"][i],
                "temp_min": d["temperature_2m_min"][i],
                "precipitation_probability": d["precipitation_probability_max"][i],
                "precipitation_sum": d["precipitation_sum"][i],
                "hourly": hours_by_date.get(d["time"][i], []),
            }
            for i in range(len(d["time"]))
        ]

        return {
            "timezone": raw.get("timezone", TIMEZONE),
            "units": {
                "temperature": "°C",
                "wind_speed": "km/h",
                "humidity": "%",
                "precipitation": "mm",
                "precipitation_probability": "%",
            },
            "current": current,
            "hourly": hourly,
            "daily": daily,
            "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }

    # ---- Public ---------------------------------------------------------------
    def get_weather(self, city: str) -> dict[str, Any]:
        location = self.resolve_city(city)
        forecast, stale = self._fetch_forecast(location["latitude"], location["longitude"])
        return {"location": location, **forecast, "stale": stale}


weather_service = WeatherService()
