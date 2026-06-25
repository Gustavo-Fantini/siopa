"""Tests for the agriculture context service."""

from app.services.agriculture_service import AgricultureService


def test_normalize_crop_key_aliases():
    service = AgricultureService()

    assert service._normalize_crop_key("Algodao") == "algodao"
    assert service._normalize_crop_key("cana-de-acucar") == "cana"
    assert service._normalize_crop_key("Soja") == "soja"


def test_merge_spray_recommendations_applies_regional_profile():
    service = AgricultureService()
    base = service.crop_database["soja"]["spray_recommendations"]
    regional_context = {"bioma": "Cerrado", "agricultural_zone": "graos_tropicais_planalto"}
    regional_profile = service._get_regional_crop_profile("soja", regional_context)

    merged = service._merge_spray_recommendations(base, regional_profile, regional_context)

    assert merged["volume_ha"] == 140
    assert merged["pressure_bar"] == 3.0
    assert "regional_note" in merged


def test_mock_soil_info_contains_context():
    service = AgricultureService()

    soil = service._get_mock_soil_info(-15.0, -47.0)

    assert soil["soil_type"]
    assert soil["location"]["bioma"]
    assert "spray_considerations" in soil["recommendations"]
