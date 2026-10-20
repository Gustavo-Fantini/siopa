"""Tests for shared droplet feature extraction."""

import cv2
import numpy as np

from app.services.vision_features import FEATURE_NAMES, extract_patch_features


def test_extract_patch_features_includes_color_and_morphology():
    patch = np.full((40, 40, 3), (0, 190, 255), dtype=np.uint8)
    cv2.circle(patch, (20, 20), 8, (150, 40, 25), -1)

    features = extract_patch_features(patch)

    assert features is not None
    assert len(features) == len(FEATURE_NAMES)
    assert features[FEATURE_NAMES.index("foreground_area")] > 0
    assert features[FEATURE_NAMES.index("center_background_delta")] > 0
