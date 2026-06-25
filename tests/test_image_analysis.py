"""Tests for the droplet image analysis pipeline."""

import os
import tempfile

import cv2
import numpy as np
import pytest

from app.core.exceptions import ImageProcessingError
from app.models.image_analysis import DropletAnalyzer


class TestDropletAnalyzer:
    """Behavioral coverage for the droplet analyzer."""

    @pytest.fixture
    def analyzer(self):
        return DropletAnalyzer()

    @pytest.fixture
    def sample_paper_image(self):
        image = np.full((720, 960, 3), 28, dtype=np.uint8)

        paper = np.array(
            [
                [140, 170],
                [810, 150],
                [835, 420],
                [120, 430],
            ],
            dtype=np.int32,
        )
        cv2.fillConvexPoly(image, paper, (0, 190, 255))

        droplet_color = (150, 40, 25)
        for center in [(245, 245), (365, 285), (610, 265), (705, 335)]:
            cv2.circle(image, center, 8, droplet_color, -1)

        # One merged mark to validate double-droplet detection.
        cv2.circle(image, (485, 240), 8, droplet_color, -1)
        cv2.circle(image, (497, 240), 8, droplet_color, -1)

        # Noise outside the paper should not matter after ROI extraction.
        cv2.line(image, (30, 40), (80, 95), (255, 255, 255), 2)

        fd, temp_path = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        cv2.imwrite(temp_path, image)

        yield temp_path
        os.unlink(temp_path)

    def test_preprocess_image_detects_paper(self, analyzer, sample_paper_image):
        image = cv2.imread(sample_paper_image)
        processed, metadata = analyzer.preprocess_image(image)

        assert processed is not None
        assert processed.ndim == 3
        assert metadata["paper_detected"] is True
        assert metadata["analysis_mm_per_px"] > 0
        assert metadata["analysis_area_px"] > 0

    def test_process_image_success(self, analyzer, sample_paper_image):
        result = analyzer.process_image(sample_paper_image)

        assert "total_droplets" in result
        assert "coverage_percentage" in result
        assert "processing_time" in result
        assert result["paper_detected"] is True
        assert result["candidate_droplets"] >= result["valid_droplets"]
        assert result["analysis_scale_mm_per_px"] > 0

    def test_double_droplets_are_flagged(self, analyzer, sample_paper_image):
        result = analyzer.process_image(sample_paper_image)
        assert result["double_droplets"] >= 1
        assert result["duplicated_droplets"] >= 1

    def test_process_nonexistent_image(self, analyzer):
        with pytest.raises(ImageProcessingError):
            analyzer.process_image("nonexistent_image.jpg")

    def test_quality_score_calculation(self, analyzer):
        score = analyzer._calculate_quality_score(20.0, 10.0, 100.0, double_ratio=0.0)
        assert 0 <= score <= 100

        bad_score = analyzer._calculate_quality_score(3.0, 55.0, 260.0, double_ratio=0.4)
        assert bad_score < score

    def test_quality_assessment(self, analyzer):
        assert analyzer._assess_quality(90) == "Excelente"
        assert analyzer._assess_quality(75) == "Boa"
        assert analyzer._assess_quality(55) == "Regular"
        assert analyzer._assess_quality(30) == "Inadequada"

    def test_generate_recommendations(self, analyzer):
        low_coverage = analyzer._generate_recommendations(4.0, 8.0, 80.0)
        assert any("Cobertura" in rec for rec in low_coverage)

        high_cv = analyzer._generate_recommendations(20.0, 20.0, 80.0)
        assert any("Distribuicao" in rec for rec in high_cv)

        doubles = analyzer._generate_recommendations(20.0, 8.0, 100.0, double_ratio=0.2)
        assert any("duplas" in rec for rec in doubles)

        ideal = analyzer._generate_recommendations(20.0, 8.0, 100.0)
        assert any("ideais" in rec.lower() or "parametros ideais" in rec.lower() for rec in ideal)


if __name__ == "__main__":
    pytest.main([__file__])
