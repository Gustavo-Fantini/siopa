"""The fuzzy score is a visible index of a chosen profile, never a probability."""
import pytest
from app.services.spray_quality import evaluate_quality


def metrics(**updates):
    base = {'coverage_percentage': 15, 'density_per_cm2': 50, 'spatial_uniformity': {'cv': 0}, 'valid_droplets': 100, 'coalesced_fraction': 0, 'calibration': {'valid': True}}
    base.update(updates)
    return base


def test_fuzzy_requires_scale_and_shows_profile_and_rules():
    assert evaluate_quality(metrics(calibration={'valid': False}))['score'] is None
    result = evaluate_quality(metrics())
    assert result['score'] == 90
    assert result['status'] == 'provisional'
    assert result['profile']['confirmed'] is False
    assert result['rules'][0]['activation'] == 1
    assert 'nao probabilidade' in result['method']


def test_confirmed_profile_is_indicative_not_a_claim_of_efficacy():
    result = evaluate_quality(metrics(), {'culture': 'soja', 'confirmed': True})
    assert result['status'] == 'indicative'
    assert result['profile']['culture'] == 'soja'
    assert result['score'] == 90
    assert any('nao mede eficacia' in message for message in result['limitations'])


def test_limiting_spatial_and_coalescence_reduce_membership():
    ideal = evaluate_quality(metrics())
    irregular = evaluate_quality(metrics(spatial_uniformity={'cv': 200}))
    coalesced = evaluate_quality(metrics(coalesced_fraction=.8))
    assert irregular['score'] < ideal['score']
    assert coalesced['score'] < ideal['score']
    assert evaluate_quality(metrics(valid_droplets=0))['score'] == 0


def test_invalid_profile_does_not_silently_change_thresholds():
    result = evaluate_quality(metrics(), {'coverageMin': 90, 'coverageTarget': 10})
    assert result['score'] is None
    assert 'Perfil invalido' in result['reason']


def test_unvalidated_catalog_profile_has_explicit_experimental_fallback():
    catalog = {'culture': 'Café', 'status': 'requires_local_calibration', 'confirmed': False}
    for key in ['coverageMin', 'coverageTarget', 'coverageMax', 'densityMin', 'densityTarget', 'densityMax', 'uniformityCvMax']:
        catalog[key] = None
    result = evaluate_quality(metrics(), catalog)
    assert result['score'] == 90
    assert result['status'] == 'provisional'
    assert result['profile_source'] == 'experimental_fallback'
    assert result['requested_profile'] == catalog
    assert result['profile']['culture'] == 'Café'
    assert result['profile']['coverageTarget'] == 15


@pytest.mark.parametrize('profile', [[], 'invalid', {'coverageTarget': None}])
def test_malformed_or_partial_null_custom_profile_is_insufficient(profile):
    result = evaluate_quality(metrics(), profile)
    assert result['score'] is None
    assert result['status'] == 'insufficient'
