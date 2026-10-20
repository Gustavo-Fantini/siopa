"""Weather normalization and persistent offline snapshots without live requests."""

import asyncio
import importlib

from app.services.weather_service import SnapshotCache, WeatherService


def test_analyze_spray_conditions_identifies_ideal_window():
    service = WeatherService()
    result = service._analyze_spray_conditions(
        {
            "temperature": 24.0,
            "humidity": 70.0,
            "wind_speed": 8.0,
            "precipitation": 0.0,
        }
    )

    assert result["overall_rating"] in {"ideal", "good"}
    assert result["score"] >= 70


def test_merge_daily_forecasts_preserves_priority_text():
    service = WeatherService()
    merged = service._merge_daily_forecasts(
        {
            "weatherapi": [
                {
                    "date": "2026-06-25",
                    "temperature": 25.0,
                    "temperature_max": 29.0,
                    "temperature_min": 19.0,
                    "humidity": 70.0,
                    "wind_speed": 8.0,
                    "precipitation": 0.0,
                    "precipitation_probability": 15.0,
                    "weather_condition": "Sol entre nuvens",
                    "source": "weatherapi",
                }
            ],
            "openweather": [
                {
                    "date": "2026-06-25",
                    "temperature": 24.0,
                    "temperature_max": 28.0,
                    "temperature_min": 18.0,
                    "humidity": 68.0,
                    "wind_speed": 10.0,
                    "precipitation": 0.5,
                    "precipitation_probability": 30.0,
                    "weather_condition": "Nublado",
                    "source": "openweather",
                }
            ],
        },
        days=1,
    )

    assert len(merged) == 1
    assert merged[0]["weather_condition"] == "Sol entre nuvens"
    assert "source_details" in merged[0]


def test_missing_weather_never_becomes_a_favorable_window():
    result = WeatherService()._analyze_spray_conditions({"temperature": 25, "wind_speed": 8})
    assert result["overall_rating"] == "unknown"
    assert result["score"] is None


def test_unavailable_weather_has_null_measurements(tmp_path, monkeypatch):
    service = WeatherService()
    service.cache = SnapshotCache(tmp_path)

    async def fail(*args, **kwargs):
        raise RuntimeError("offline")

    monkeypatch.setattr(service, "_get_open_meteo_bundle", fail)
    monkeypatch.setattr(service, "_get_weather_from_apis", fail)
    monkeypatch.setattr(service, "_get_forecast_from_apis", fail)
    current = asyncio.run(service.get_current_weather(-22, -49))
    assert current["availability"] == "unavailable"
    assert current["temperature"] is None
    assert current["spray_conditions"]["overall_rating"] == "unknown"
    assert asyncio.run(service.get_weather_forecast(-22, -49)) == []


def test_open_meteo_current_and_forecast_share_request(tmp_path, monkeypatch):
    service = WeatherService()
    service.cache = SnapshotCache(tmp_path)
    calls = []

    async def response(*args, **kwargs):
        calls.append(kwargs["params"])
        return {"latitude": -22.1, "longitude": -49.1,
                "current": {"time": "2026-10-20T12:00", "interval": 900, "temperature_2m": 24,
                            "relative_humidity_2m": 60, "wind_speed_10m": 7, "precipitation": 0},
                "hourly": {"time": ["2026-10-20T12:00", "2026-10-20T13:00"],
                           "temperature_2m": [24, 26], "relative_humidity_2m": [60, 56],
                           "wind_speed_10m": [7, 9], "precipitation": [0, 0.4]}}

    monkeypatch.setattr(service, "_request_json", response)
    current = asyncio.run(service.get_current_weather(-22, -49))
    forecast = asyncio.run(service.get_weather_forecast(-22, -49))
    assert len(calls) == 1
    assert current["data_kind"] == "weather_model"
    assert current["source"] == "open_meteo"
    assert current["precipitation_interval_seconds"] == 900
    assert forecast[0]["temperature"] == 25
    assert forecast[0]["precipitation"] == 0.4
    assert forecast[0]["spray_conditions"]["overall_rating"] == "unknown"


def test_snapshot_survives_restart_and_failed_refresh(tmp_path, monkeypatch):
    module = importlib.import_module("app.services.weather_service")
    clock = [1000.0]
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    first = SnapshotCache(tmp_path)

    async def online():
        return {"availability": "available", "temperature": 19}

    initial = asyncio.run(first.resolve("point", online, 60, {"availability": "unavailable"}))
    clock[0] = 1061
    restored = SnapshotCache(tmp_path)
    calls = []

    async def offline():
        calls.append(1)
        raise RuntimeError("offline")

    stale = asyncio.run(restored.resolve("point", offline, 60, {"availability": "unavailable"}))
    repeated = asyncio.run(restored.resolve("point", offline, 60, {"availability": "unavailable"}))
    assert stale["stale"] is True
    assert stale["temperature"] == 19
    assert stale["fetched_at"] == initial["fetched_at"]
    assert repeated["refresh_failed"] is True
    assert len(calls) == 1


def test_concurrent_snapshot_requests_share_provider_and_keep_source(tmp_path):
    cache = SnapshotCache(tmp_path)
    calls = []

    async def provider():
        calls.append(1)
        await asyncio.sleep(0)
        return {"availability": "available", "source": "verified_provider", "timestamp": "2026-10-20T20:00:00Z"}

    async def fetch_pair():
        return await asyncio.gather(*[cache.resolve("same-point", provider, 60, {"availability": "unavailable"}) for _ in range(2)])

    first, second = asyncio.run(fetch_pair())
    assert len(calls) == 1
    assert first["source"] == second["source"] == "verified_provider"
    assert first["timestamp"] == second["timestamp"] == "2026-10-20T20:00:00Z"
    assert first["fetched_at"] == second["fetched_at"]
    assert first["stale"] is False and second["cached"] is True
