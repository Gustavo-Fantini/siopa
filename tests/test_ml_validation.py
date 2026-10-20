import numpy as np
import pytest

from app.services.ml_training import split_by_source_image


def test_patches_and_duplicate_source_images_never_cross_holdout():
    groups = np.repeat(["same-photo-hash", "second-photo", "third-photo", "fourth-photo"], 8)
    X = np.arange(len(groups) * 2).reshape(-1, 2)
    y = np.tile([0, 1], len(groups) // 2)
    train, test = split_by_source_image(X, y, groups, 0.25)
    assert set(groups[train]).isdisjoint(set(groups[test]))
    assert set(train) | set(test) == set(range(len(X)))


def test_duplicate_only_dataset_cannot_claim_independent_validation():
    with pytest.raises(ValueError, match="distintas"):
        split_by_source_image(np.ones((8, 2)), np.tile([0, 1], 4), ["same-photo"] * 8)
