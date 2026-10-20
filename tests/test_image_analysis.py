"""Behavioral and cross-runtime checks for the offline stain measurements."""
import json
import os
from pathlib import Path
import shutil
import subprocess

import cv2
import numpy as np
from PIL import Image
import pytest

from app.core.exceptions import ImageProcessingError
from app.models.image_analysis import DropletAnalyzer
from app.services.spray_quality import evaluate_quality


@pytest.fixture
def analyzer():
    return DropletAnalyzer()


@pytest.fixture
def collector():
    image = np.full((120, 240, 3), (0, 190, 255), np.uint8)
    for center in [(25, 25), (65, 25), (105, 25), (145, 25), (185, 25), (215, 25)]:
        cv2.circle(image, center, 4, (150, 40, 25), -1)
    cv2.circle(image, (80, 75), 7, (150, 40, 25), -1)
    cv2.circle(image, (90, 75), 7, (150, 40, 25), -1)
    cv2.circle(image, (2, 90), 5, (150, 40, 25), -1)
    cv2.circle(image, (160, 75), 1, (150, 40, 25), -1)
    return image


def analyze(analyzer, image, **options):
    rgb, metadata = analyzer.preprocess_image(image, options)
    return analyzer.analyze_droplets(analyzer.segment_droplets(rgb, metadata), metadata)


def test_counts_exclude_merged_edge_and_unresolved_stains(analyzer, collector):
    result = analyze(analyzer, collector, mmPerPixel=.02, includeOverlayPixels=False)
    assert result['valid_droplets'] == 6
    assert result['coalesced_components'] == 1
    assert result['edge_droplets'] == 1
    assert result['rejected_by_size'] == 1
    assert {part['label'] for part in result['overlay']['components']} == {'valid', 'coalesced', 'edge'}
    assert result['dv50_diameter'] is None
    assert result['stain_diameter']['spread_factor_applied'] is False


def test_coverage_is_observed_stain_pixels_without_expansion(analyzer, collector):
    result = analyze(analyzer, collector, mmPerPixel=.02, includeOverlayPixels=False)
    rgb, metadata = analyzer.preprocess_image(collector, {'mmPerPixel': .02})
    mask = analyzer.segment_droplets(rgb, metadata)
    margin = metadata['border_margin_px']
    # The five-pixel dot is below the resolution threshold; all other stained pixels
    # contribute to coverage, including coalescence and the in-ROI part of an edge hit.
    expected_pixels = int(mask[margin:-margin, margin:-margin].sum()) - 5
    assert result['coverage_percentage'] == pytest.approx(expected_pixels / result['analysis_area_px'] * 100, abs=.001)
    assert result['density_per_cm2'] == pytest.approx(6 / (result['analysis_area_px'] * .02 ** 2 / 100), abs=.001)


def test_missing_calibration_never_invents_physical_units_or_quality(analyzer, collector):
    result = analyze(analyzer, collector, includeOverlayPixels=False)
    assert result['calibration']['valid'] is False
    assert result['analysis_scale_mm_per_px'] is None
    assert result['density_per_cm2'] is None
    assert result['mean_diameter'] is None
    assert result['quality_score'] is None
    assert result['quality']['status'] == 'insufficient'
    assert result['coverage_percentage'] >= 0


def test_physical_minimum_is_configurable_and_does_not_expand_coverage(analyzer, collector):
    ordinary = analyze(analyzer, collector, mmPerPixel=.02, minStainDiameterMm=.10, includeOverlayPixels=False)
    restricted = analyze(analyzer, collector, mmPerPixel=.02, minStainDiameterMm=.25, includeOverlayPixels=False)
    assert restricted['valid_droplets'] < ordinary['valid_droplets']
    assert restricted['coverage_percentage'] == ordinary['coverage_percentage']


def test_effective_minimum_reports_pixel_floor_and_cannot_create_missing_detail(analyzer, collector):
    scale = 76 / 1200
    result = analyze(analyzer, collector, mmPerPixel=scale, minStainDiameterMm=.10, includeOverlayPixels=False)
    lowered = analyze(analyzer, collector, mmPerPixel=scale, minStainDiameterMm=.01, includeOverlayPixels=False)
    expected = 2 * np.sqrt(9 / np.pi) * scale
    assert result['effective_min_stain_diameter_mm'] == pytest.approx(expected, abs=.000001)
    assert lowered['effective_min_stain_diameter_mm'] == result['effective_min_stain_diameter_mm']
    assert lowered['valid_droplets'] == result['valid_droplets']
    assert any('piso de pixels' in warning for warning in result['warnings'])


def test_portrait_paper_retains_physical_long_axis(analyzer):
    horizontal = np.full((180, 380, 3), 25, np.uint8)
    cv2.rectangle(horizontal, (40, 40), (340, 140), (0, 190, 255), -1)
    for center in [(90, 80), (180, 90), (280, 100)]:
        cv2.circle(horizontal, center, 4, (150, 40, 25), -1)
    vertical = cv2.rotate(horizontal, cv2.ROTATE_90_CLOCKWISE)
    first = analyze(analyzer, horizontal, paperSizeConfirmed=True, includeOverlayPixels=False)
    second = analyze(analyzer, vertical, paperSizeConfirmed=True, includeOverlayPixels=False)
    assert first['paper_detected'] and second['paper_detected']
    assert first['valid_droplets'] == second['valid_droplets'] == 3
    assert first['overlay']['width'] > first['overlay']['height']
    assert second['overlay']['width'] > second['overlay']['height']
    assert first['mean_diameter'] == pytest.approx(second['mean_diameter'], rel=.04)


def test_spatial_cv_distinguishes_clustered_from_even_counts(analyzer):
    uniform = np.full((120, 240, 3), (0, 190, 255), np.uint8)
    clustered = uniform.copy()
    for y in [22, 60, 98]:
        for x in [22, 61, 100, 139, 178, 217]:
            cv2.circle(uniform, (x, y), 3, (150, 40, 25), -1)
    for y in [14, 25, 36]:
        for x in [10, 21, 32, 43, 54, 65]:
            cv2.circle(clustered, (x, y), 3, (150, 40, 25), -1)
    a = analyze(analyzer, uniform, mmPerPixel=.02, includeOverlayPixels=False)
    b = analyze(analyzer, clustered, mmPerPixel=.02, includeOverlayPixels=False)
    assert a['valid_droplets'] == b['valid_droplets'] == 18
    assert a['spatial_uniformity']['cv'] == 0
    assert b['spatial_uniformity']['cv'] > 100


def test_exif_orientation_applied_before_analysis(analyzer, collector, tmp_path):
    path = tmp_path / 'phone.jpg'
    exif = Image.Exif()
    exif[274] = 6
    Image.fromarray(cv2.cvtColor(collector, cv2.COLOR_BGR2RGB)).save(path, exif=exif, quality=100)
    result = analyzer.process_image(str(path), {'mmPerPixel': .02, 'includeOverlayPixels': False})
    assert result['overlay']['width'] == collector.shape[0]
    assert result['overlay']['height'] == collector.shape[1]
    assert result['orientation_applied'].startswith('EXIF')


def test_invalid_path_and_invalid_corners(analyzer, tmp_path, collector):
    with pytest.raises(ImageProcessingError):
        analyzer.process_image(str(tmp_path / 'absent.jpg'))
    with pytest.raises(ImageProcessingError):
        analyzer.preprocess_image(collector, {'paperCorners': [[0, 0], [1, 1], [2, 2], [3, 3]]})


@pytest.mark.parametrize('options', [
    {'paperSizeConfirmed': True, 'paperWidthMm': -76},
    {'paperSizeConfirmed': True, 'paperHeightMm': float('inf')},
    {'mmPerPixel': 0},
])
def test_invalid_explicit_scale_is_rejected_instead_of_assuming_default(analyzer, collector, options):
    with pytest.raises(ImageProcessingError):
        analyzer.preprocess_image(collector, options)


def test_volume_proxy_uses_cubic_weights_not_number_median(analyzer):
    assert analyzer._volume_quantile([100, 100, 300], .5) == 300


def _node_runtime():
    executable = shutil.which('node')
    if executable:
        return executable, dict(os.environ)
    vscode = Path(os.environ.get('LOCALAPPDATA', '')) / 'Programs/Microsoft VS Code/Code.exe'
    if vscode.is_file():
        return str(vscode), dict(os.environ, ELECTRON_RUN_AS_NODE='1')
    pytest.skip('Node runtime unavailable; Python measurements tested separately')


@pytest.mark.parametrize('mode', ['manual', 'uncalibrated', 'rectified', 'portrait'])
def test_javascript_python_parity_for_counts_units_coverage_and_fuzzy(analyzer, collector, mode):
    runtime, environment = _node_runtime()
    options = {'includeOverlayPixels': False}
    if mode == 'manual':
        options['mmPerPixel'] = .02
    elif mode in {'rectified', 'portrait'}:
        options.update(paperSizeConfirmed=True, paperWidthMm=4.8, paperHeightMm=2.4)
        if mode == 'portrait':
            collector = cv2.rotate(collector, cv2.ROTATE_90_CLOCKWISE)
        height, width = collector.shape[:2]
        options['paperCorners'] = [[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]
    rgba = cv2.cvtColor(collector, cv2.COLOR_BGR2RGBA)
    fixture = {'width': rgba.shape[1], 'height': rgba.shape[0], 'data': rgba.flatten().tolist(), 'options': options}
    script = Path(__file__).parent / 'vision_parity_runner.js'
    completed = subprocess.run([runtime, str(script)], input=json.dumps(fixture), text=True, encoding='utf-8', capture_output=True, env=environment, timeout=30, check=True)
    portable = json.loads(completed.stdout)
    native = analyze(analyzer, collector, **options)
    for key in ['valid_droplets', 'coalesced_components', 'edge_droplets', 'rejected_by_size', 'analysis_area_px']:
        assert portable[key] == native[key], key
    for key in ['coverage_percentage', 'density_per_cm2', 'cv_coefficient', 'dv50_proxy_um', 'quality_score', 'effective_min_stain_diameter_mm']:
        if native[key] is None:
            assert portable[key] is None, key
        else:
            assert portable[key] == pytest.approx(native[key], abs=.1), key
    assert portable['quality']['status'] == native['quality']['status']
    assert portable['spatial_uniformity']['counts'] == native['spatial_uniformity']['counts']
