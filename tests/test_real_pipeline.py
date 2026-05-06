"""Integration tests that run inference against the real HuggingFace model.

Run with:
    pytest tests/test_real_pipeline.py -v --real-model

Skipped by default to avoid the ~400 MB model download in CI.
"""

import pytest
from PIL import Image, ImageDraw

from modules.ai_detector import AIImageDetector


@pytest.fixture(scope="module")
def real_detector(request):
    if not request.config.getoption("--real-model"):
        pytest.skip("Pass --real-model to run real pipeline tests")
    return AIImageDetector()


def _solid_image(color: tuple, size: tuple = (256, 256)) -> Image.Image:
    return Image.new("RGB", size, color=color)


def _gradient_image(size: tuple = (256, 256)) -> Image.Image:
    img = Image.new("RGB", size)
    draw = ImageDraw.Draw(img)
    for x in range(size[0]):
        shade = int(x / size[0] * 255)
        draw.line([(x, 0), (x, size[1])], fill=(shade, shade, shade))
    return img


class TestRealPipeline:
    def test_returns_expected_keys(self, real_detector):
        img = _solid_image((128, 128, 128))
        result = real_detector.analyze_image(img)
        assert set(result.keys()) == {
            "is_ai", "confidence", "verdict", "full_analysis",
            "fake_probability", "real_probability", "processing_time_ms",
        }

    def test_probabilities_sum_to_one(self, real_detector):
        img = _solid_image((200, 100, 50))
        result = real_detector.analyze_image(img)
        total = result["fake_probability"] + result["real_probability"]
        assert abs(total - 1.0) < 0.01

    def test_confidence_matches_verdict(self, real_detector):
        img = _gradient_image()
        result = real_detector.analyze_image(img)
        if result["verdict"] == "Likely AI":
            assert result["confidence"] == pytest.approx(result["fake_probability"])
            assert result["confidence"] > 0.6
        elif result["verdict"] == "Likely Real":
            assert result["confidence"] == pytest.approx(result["real_probability"])
            assert result["confidence"] > 0.6
        else:
            assert result["verdict"] == "Uncertain"
            assert result["confidence"] <= 0.6

    def test_processing_time_positive(self, real_detector):
        img = _solid_image((0, 0, 0))
        result = real_detector.analyze_image(img)
        assert result["processing_time_ms"] > 0

    def test_rgba_input_handled(self, real_detector):
        img = Image.new("RGBA", (256, 256), color=(128, 128, 128, 255))
        result = real_detector.analyze_image(img)
        assert "verdict" in result

    def test_large_image_resized_and_analyzed(self, real_detector):
        img = _solid_image((100, 150, 200), size=(2048, 2048))
        result = real_detector.analyze_image(img)
        assert "verdict" in result

    def test_model_info(self, real_detector):
        info = real_detector.get_model_info()
        assert info["name"] == "umm-maybe/AI-image-detector"
        assert info["accuracy"] == "94.2%"
        assert info["device"] in ("cpu", "cuda")
