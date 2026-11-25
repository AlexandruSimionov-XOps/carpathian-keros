"""WeatherService: city resolution, upstream calls, payload shaping, caching and stale fallback."""

from __future__ import annotations

import pytest
import requests

from services.weather_service import (
    FORECAST_URL,
    REQUEST_TIMEOUT,
    CityNotFoundError,
    InvalidCityError,
    TTLCache,
    UpstreamError,
    WeatherService,
    WeatherServiceError,
)


def test_get_weather_returns_the_documented_shape(service):
    data = service.get_weather("Iași")
    assert set(data) == {"location", "timezone", "units", "current", "hourly", "daily", "fetched_at", "stale"}
    assert data["location"]["name"] == "Iași"
    assert data["location"]["query"] == "Iași"
    assert set(data["current"]) == {
        "time",
        "temperature",
        "feels_like",
        "humidity",
        "wind_speed",
        "weather_code",
        "is_day",
    }
    assert len(data["hourly"]) == 24
    assert len(data["daily"]) == 7
    assert data["stale"] is False


def test_hourly_starts_at_the_current_local_hour(service, forecast_payload):
    data = service.get_weather("Iași")
    assert data["hourly"][0]["time"] == forecast_payload["current"]["time"][:13] + ":00"


def test_api_values_are_not_rounded(service, fake_session):
    fake_session.payload["current"]["temperature_2m"] = 3.5
    assert service.get_weather("Oradea")["current"]["temperature"] == 3.5


def test_only_the_forecast_host_is_called_with_registry_coordinates(service, fake_session, registry):
    """Regression guard: the app must never geocode at runtime (Article V.2: one outbound host)."""
    service.get_weather("Cluj-Napoca")
    assert len(fake_session.calls) == 1
    url, params = fake_session.calls[0]
    assert url == FORECAST_URL
    city = registry.resolve("Cluj-Napoca")
    assert (params["latitude"], params["longitude"]) == (city.latitude, city.longitude)
    assert params["timezone"] == "Europe/Bucharest"


def test_requests_always_carry_a_timeout(registry):
    seen = {}

    class RecordingSession:
        def get(self, url, params=None, timeout=None):
            seen["timeout"] = timeout
            raise requests.ConnectionError("offline")

    with pytest.raises(UpstreamError):
        WeatherService(session=RecordingSession(), registry=registry).get_weather("Iași")
    assert seen["timeout"] == REQUEST_TIMEOUT


@pytest.mark.parametrize(
    ("query", "error"),
    [
        ("", InvalidCityError),
        ("x" * 101, InvalidCityError),
        ("Atlantis", CityNotFoundError),
        ("Florești", CityNotFoundError),
    ],
)
def test_invalid_or_unlisted_cities_never_reach_the_network(service, fake_session, query, error):
    with pytest.raises(error):
        service.get_weather(query)
    assert fake_session.calls == []


@pytest.mark.parametrize(
    ("cls", "code", "status"),
    [
        (InvalidCityError, "invalid_city", 400),
        (CityNotFoundError, "city_not_found", 404),
        (UpstreamError, "upstream_error", 502),
    ],
)
def test_error_types_honour_the_base_contract(cls, code, status):
    """Liskov (Article I): every subclass is usable wherever WeatherServiceError is handled."""
    assert issubclass(cls, WeatherServiceError)
    assert (cls.code, cls.status) == (code, status)


class TestCaching:
    def test_spellings_of_one_city_share_a_cache_entry(self, service, fake_session):
        service.get_weather("Iași")
        service.get_weather("iasi")
        assert len(fake_session.calls) == 1

    def test_entry_expires_after_the_ttl(self, service, fake_session, clock):
        service.get_weather("Iași")
        clock.advance(599)
        service.get_weather("Iași")
        assert len(fake_session.calls) == 1
        clock.advance(2)
        service.get_weather("Iași")
        assert len(fake_session.calls) == 2

    def test_stale_entry_is_served_when_upstream_fails(self, service, fake_session, clock):
        service.get_weather("Iași")
        clock.advance(601)
        fake_session.error = requests.ConnectionError("down")
        data = service.get_weather("Iași")
        assert data["stale"] is True
        assert data["location"]["name"] == "Iași"

    def test_upstream_failure_without_cache_is_an_upstream_error(self, service, fake_session):
        fake_session.error = requests.Timeout("slow")
        with pytest.raises(UpstreamError):
            service.get_weather("Iași")

    def test_http_error_status_is_an_upstream_error(self, service, fake_session):
        fake_session.status_code = 503
        with pytest.raises(UpstreamError):
            service.get_weather("Iași")

    def test_malformed_payload_is_an_upstream_error(self, service, fake_session):
        del fake_session.payload["current"]
        with pytest.raises(UpstreamError):
            service.get_weather("Iași")

    def test_provider_error_body_is_an_upstream_error(self, service, fake_session):
        fake_session.payload = {"error": True, "reason": "bad request"}
        with pytest.raises(UpstreamError):
            service.get_weather("Iași")


class TestTTLCache:
    def test_get_returns_only_fresh_entries_but_get_stale_keeps_them(self, clock):
        cache = TTLCache(10, clock=clock)
        cache.set("k", 1)
        assert cache.get("k") == 1
        clock.advance(11)
        assert cache.get("k") is None
        assert cache.get_stale("k") == 1

    def test_size_bound_evicts_oldest_writes(self, clock):
        cache = TTLCache(10, max_entries=2, clock=clock)
        for key in ("a", "b", "c"):
            cache.set(key, key)
        assert cache.get_stale("a") is None
        assert cache.get("b") == "b" and cache.get("c") == "c"

    def test_clear_empties_the_cache(self, clock):
        cache = TTLCache(10, clock=clock)
        cache.set("k", 1)
        cache.clear()
        assert cache.get_stale("k") is None


def test_each_day_carries_its_own_24_hours(service, forecast_payload):
    """daily[].hourly (additive, v1-compatible) powers the 'click a day' view: 00:00–23:00 local time."""
    data = service.get_weather("Iași")
    for day in data["daily"]:
        hours = day["hourly"]
        assert [h["time"] for h in hours] == [f"{day['date']}T{h:02d}:00" for h in range(24)]
        assert set(hours[0]) == {"time", "temperature", "precipitation", "precipitation_probability", "weather_code"}
    # the existing top-level contract is unchanged
    assert len(data["hourly"]) == 24
    assert data["hourly"][0]["time"] == forecast_payload["current"]["time"][:13] + ":00"
