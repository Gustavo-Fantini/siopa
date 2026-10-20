"""Crop identity and honest missing soil context, without network calls."""

import asyncio

from app.services.agriculture_service import AgricultureService
from app.services.crop_catalog import CropCatalog


def test_normalize_crop_key_aliases():
    service = AgricultureService()
    assert service._normalize_crop_key('Algodão') == 'algodao'
    assert service._normalize_crop_key('cana-de-açúcar') == 'cana'
    assert service._normalize_crop_key('rice') == 'arroz'
    assert service._normalize_crop_key('grape') == 'uva'


def test_catalog_is_broad_and_does_not_invent_thresholds():
    catalog = CropCatalog()
    crops = catalog.list_crops()
    assert len(crops) >= 80
    assert len({crop['key'] for crop in crops}) == len(crops)
    for crop in crops:
        assert crop['scientific_name'] and crop['aliases'] and crop['growth_stages'] and crop['sources']
        profile = catalog.quality_profile(crop)
        assert profile['confirmed'] is False
        assert profile['coverageMin'] is None
        assert profile['densityTarget'] is None
        assert 'dosage' not in crop


def test_culture_and_location_do_not_infer_soil_or_product():
    crop = asyncio.run(AgricultureService().get_crop_info('arroz', latitude=-15, longitude=-47))
    assert crop['name'] == 'Arroz'
    assert crop['spray_recommendations']['volume_ha'] is None
    assert crop['regional_context']['bioma'] is None
    assert crop['regional_context']['municipio'] is None
    assert crop['quality_profile']['status'] == 'requires_local_calibration'


def test_unknown_culture_remains_unknown():
    result = asyncio.run(AgricultureService().get_crop_info('cultura inexistente'))
    assert result['status'] == 'not_catalogued'
    assert result['scientific_name'] is None
    assert result['quality_profile']['confirmed'] is False