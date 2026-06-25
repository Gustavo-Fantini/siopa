"""Tests for weather service pure logic."""

from app.services.weather_service import WeatherService


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
