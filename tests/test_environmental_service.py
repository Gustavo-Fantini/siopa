"""Regional data normalization, missing components and provider request budgets."""

import asyncio

from app.services.environmental_service import EnvironmentalService


def test_soil_units_and_uncertainty_are_explicit(tmp_path):
    result = EnvironmentalService(tmp_path)._normalize_soil({"properties": {"layers": [
        {"name": "phh2o", "depths": [{"label": "0-5cm", "values": {"mean": 58, "Q0.05": 47, "Q0.95": 69}}]},
        {"name": "sand", "depths": [{"label": "0-5cm", "values": {"mean": 432, "Q0.05": None, "Q0.95": 810}}]}
    ]}})
    assert result["ph"] == 5.8
    assert result["properties"]["sand"]["depths"]["0-5cm"]["mean"] == 43.2
    assert result["properties"]["phh2o"]["depths"]["0-5cm"]["q05"] == 4.7
    assert result["soil_type"] is None
    assert result["observed_at"] is None
    assert result["availability"] == "partial"
    assert "250" in result["resolution"]


def test_failed_soil_and_terrain_are_explicit_and_cached(tmp_path, monkeypatch):
    service = EnvironmentalService(tmp_path)
    calls = []

    async def offline(*args, **kwargs):
        calls.append(1)
        raise RuntimeError("offline")

    monkeypatch.setattr(service, "_request_json", offline)
    soil = asyncio.run(service.get_soil(-22, -49))
    terrain = asyncio.run(service.get_terrain(-22, -49))
    asyncio.run(service.get_soil(-22, -49))
    assert len(calls) == 2
    assert soil["availability"] == "unavailable"
    assert soil["properties"] == {}
    assert soil["ph"] is None
    assert terrain["elevation_m"] is None
    assert terrain["slope_degrees"] is None


def test_terrain_reports_dem_not_surveyed_slope(tmp_path, monkeypatch):
    service = EnvironmentalService(tmp_path)

    async def response(*args, **kwargs):
        return {"elevation": [580.4]}

    monkeypatch.setattr(service, "_request_json", response)
    result = asyncio.run(service.get_terrain(-22, -49))
    assert result["elevation_m"] == 580.4
    assert result["slope_degrees"] is None
    assert result["provenance"][0]["data_kind"] == "digital_surface_model"
    assert result["fetched_at"] and result["expires_at"]


def test_invalid_coordinates_do_not_call_provider(tmp_path):
    service = EnvironmentalService(tmp_path)
    for latitude, longitude in ((91, 0), (0, 181), (float("nan"), 0)):
        try:
            asyncio.run(service.get_soil(latitude, longitude))
        except ValueError:
            pass
        else:
            raise AssertionError("Coordenadas inválidas aceitas")


def test_soil_budget_caps_requests_for_new_locations(tmp_path, monkeypatch):
    service = EnvironmentalService(tmp_path)
    calls = []

    async def response(*args, **kwargs):
        calls.append(1)
        return {"properties": {"layers": [{"name": "phh2o", "depths": [
            {"label": "0-5cm", "values": {"mean": 60}}
        ]}]}}

    monkeypatch.setattr(service, "_request_json", response)

    async def fetch_many():
        return [await service.get_soil(-22, -49 + i * 0.01) for i in range(6)]

    results = asyncio.run(fetch_many())
    assert len(calls) == 5
    assert results[-1]["availability"] == "unavailable"
