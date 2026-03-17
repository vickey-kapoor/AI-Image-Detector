"""Shared test fixtures for AI Image Detector."""

from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from modules.ai_detector import AIImageDetector


@pytest.fixture
def sample_image():
    """Create a simple RGB test image."""
    return Image.new("RGB", (256, 256), color=(128, 128, 128))


@pytest.fixture
def sample_rgba_image():
    """Create a simple RGBA test image."""
    return Image.new("RGBA", (256, 256), color=(128, 128, 128, 255))


@pytest.fixture
def large_image():
    """Create an oversized test image."""
    return Image.new("RGB", (4000, 3000), color=(200, 100, 50))


@pytest.fixture
def mock_classifier():
    """Mock HuggingFace pipeline that returns AI detection results."""
    classifier = MagicMock()
    classifier.return_value = [
        {"label": "artificial", "score": 0.85},
        {"label": "human", "score": 0.15},
    ]
    return classifier


@pytest.fixture
def mock_detector(mock_classifier):
    """Create an AIImageDetector with mocked model."""
    with patch("modules.ai_detector.pipeline", return_value=mock_classifier):
        with patch("modules.ai_detector.torch") as mock_torch:
            mock_torch.cuda.is_available.return_value = False
            detector = AIImageDetector()
    return detector


@pytest.fixture
def mock_result_ai():
    """Sample AI-detected result dict."""
    return {
        "is_ai": True,
        "confidence": 0.85,
        "verdict": "Likely AI",
        "full_analysis": "AI: 85.0%, Human: 15.0%",
        "fake_probability": 0.85,
        "real_probability": 0.15,
        "processing_time_ms": 42.5,
    }


@pytest.fixture
def mock_result_real():
    """Sample real-image result dict."""
    return {
        "is_ai": False,
        "confidence": 0.92,
        "verdict": "Likely Real",
        "full_analysis": "AI: 8.0%, Human: 92.0%",
        "fake_probability": 0.08,
        "real_probability": 0.92,
        "processing_time_ms": 38.1,
    }
