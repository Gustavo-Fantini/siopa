import json

import pytest

from scripts.evaluate_counts import evaluate


def test_human_count_report_preserves_bias_and_does_not_invent_detection_accuracy(tmp_path):
    images = []
    for name, expected in (("one.jpg", 8), ("two.jpg", 12)):
        (tmp_path / name).write_bytes(b"fixture handled by analyzer")
        images.append({"image_path": name, "expected_isolated_count": expected})
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"schema_version": 1, "images": images}))
    class Analyzer:
        def process_image(self, path, options):
            return {"valid_droplets": 10, "measurement_status": "calibrated", "engine_version": "fixture"}
    report = evaluate(manifest, Analyzer())
    assert report["metrics"]["count_mae"] == 2
    assert report["metrics"]["count_bias"] == 0
    assert report["metrics"]["exact_count_matches"] == 0
    assert "precision" not in report["metrics"]


def test_unfilled_example_cannot_be_reported_as_measured_ground_truth(tmp_path):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps({"schema_version": 1, "images": [{"image_path": "none.jpg", "expected_isolated_count": None}]}))
    with pytest.raises(ValueError, match="contagem humana"):
        evaluate(path)
