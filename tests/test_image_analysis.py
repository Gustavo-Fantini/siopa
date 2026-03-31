"""
Testes para o módulo de análise de imagens.
"""

import os
import tempfile

import cv2
import numpy as np
import pytest

from app.core.exceptions import ImageProcessingError
from app.models.image_analysis import DropletAnalyzer


class TestDropletAnalyzer:
    """Testes para o analisador de gotículas."""

    @pytest.fixture
    def analyzer(self):
        return DropletAnalyzer()

    @pytest.fixture
    def sample_image(self):
        img = np.zeros((512, 512, 3), dtype=np.uint8)
        img.fill(255)

        centers = [(100, 100), (200, 150), (300, 200), (150, 300)]
        for center in centers:
            cv2.circle(img, center, 15, (255, 0, 0), -1)

        temp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        cv2.imwrite(temp_file.name, img)

        yield temp_file.name
        os.unlink(temp_file.name)

    def test_preprocess_image(self, analyzer, sample_image):
        img = cv2.imread(sample_image)
        processed, metadata = analyzer.preprocess_image(img)

        assert processed is not None
        assert processed.shape == analyzer.input_size + (3,)
        assert "original_shape" in metadata
        assert "scale" in metadata

    def test_process_image_success(self, analyzer, sample_image):
        result = analyzer.process_image(sample_image)
        assert "total_droplets" in result
        assert "coverage_percentage" in result
        assert "processing_time" in result

    def test_process_nonexistent_image(self, analyzer):
        with pytest.raises(ImageProcessingError):
            analyzer.process_image("nonexistent_image.jpg")

    def test_quality_score_calculation(self, analyzer):
        score = analyzer._calculate_quality_score(20.0, 10.0, 100.0)
        assert 0 <= score <= 100

        bad_score = analyzer._calculate_quality_score(3.0, 55.0, 260.0)
        assert bad_score < score

    def test_quality_assessment(self, analyzer):
        assert analyzer._assess_quality(90) == "Excelente"
        assert analyzer._assess_quality(75) == "Boa"
        assert analyzer._assess_quality(55) == "Regular"
        assert analyzer._assess_quality(30) == "Inadequada"

    def test_generate_recommendations(self, analyzer):
        low_coverage = analyzer._generate_recommendations(4.0, 8.0, 80.0)
        assert any("cobertura" in rec.lower() for rec in low_coverage)

        high_cv = analyzer._generate_recommendations(20.0, 20.0, 80.0)
        assert any("calibra" in rec.lower() for rec in high_cv)

        ideal = analyzer._generate_recommendations(20.0, 8.0, 100.0)
        assert any("ideais" in rec.lower() for rec in ideal)


if __name__ == "__main__":
    pytest.main([__file__])
