"""Tests for AIImageDetector module."""

from PIL import Image

from modules.ai_detector import MAX_IMAGE_DIMENSION, AIImageDetector


class TestAIImageDetector:
    def test_analyze_returns_expected_keys(self, mock_detector, sample_image):
        result = mock_detector.analyze_image(sample_image)
        expected_keys = {
            "is_ai", "confidence", "verdict", "full_analysis",
            "fake_probability", "real_probability", "processing_time_ms",
        }
        assert set(result.keys()) == expected_keys

    def test_ai_detection(self, mock_detector, sample_image):
        # Classifier returns high artificial score (set in conftest)
        result = mock_detector.analyze_image(sample_image)
        assert result["is_ai"] is True
        assert result["verdict"] == "Likely AI"
        assert result["confidence"] == 0.85

    def test_real_detection(self, mock_detector, sample_image):
        mock_detector.classifier.return_value = [
            {"label": "artificial", "score": 0.1},
            {"label": "human", "score": 0.9},
        ]
        result = mock_detector.analyze_image(sample_image)
        assert result["is_ai"] is False
        assert result["verdict"] == "Likely Real"
        assert result["confidence"] == 0.9

    def test_uncertain_detection(self, mock_detector, sample_image):
        mock_detector.classifier.return_value = [
            {"label": "artificial", "score": 0.55},
            {"label": "human", "score": 0.45},
        ]
        result = mock_detector.analyze_image(sample_image)
        assert result["is_ai"] is False
        assert result["verdict"] == "Uncertain"

    def test_rgba_conversion(self, mock_detector, sample_rgba_image):
        result = mock_detector.analyze_image(sample_rgba_image)
        assert result["is_ai"] is True  # Still works with RGBA input

    def test_resize_large_image(self, mock_detector, large_image):
        result = mock_detector.analyze_image(large_image)
        # Should not raise, image is resized internally
        assert "is_ai" in result

    def test_resize_preserves_small_images(self):
        img = Image.new("RGB", (200, 200))
        resized = AIImageDetector._resize_if_needed(img)
        assert resized.size == (200, 200)

    def test_resize_shrinks_oversized(self):
        img = Image.new("RGB", (2048, 1024))
        resized = AIImageDetector._resize_if_needed(img)
        assert resized.size[0] <= MAX_IMAGE_DIMENSION
        assert resized.size[1] <= MAX_IMAGE_DIMENSION

    def test_get_model_info(self, mock_detector):
        info = mock_detector.get_model_info()
        assert info["name"] == "umm-maybe/AI-image-detector"
        assert info["accuracy"] == "94.2%"
        assert "device" in info

    def test_processing_time_recorded(self, mock_detector, sample_image):
        result = mock_detector.analyze_image(sample_image)
        assert result["processing_time_ms"] > 0
