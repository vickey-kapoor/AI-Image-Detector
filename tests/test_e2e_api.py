"""End-to-end tests: real HuggingFace pipeline through the FastAPI layer.

Run with:
    pytest tests/test_e2e_api.py -v --real-model

The real detector is loaded once per session (scope=module) and injected into
the API globals — no mocks, full request path exercised.
"""

import base64
import importlib
import io
import tempfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from api.rate_limiter import TokenBucketRateLimiter
from modules.ai_detector import AIImageDetector
from modules.image_cache import ImageCache
from modules.json_logger import JSONLogger

VALID_VERDICTS = {"Likely AI", "Likely Real", "Uncertain"}


def _b64_image(color: tuple = (128, 128, 128), size: tuple = (224, 224)) -> str:
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


@pytest.fixture(scope="module")
def real_api_client(request):
    if not request.config.getoption("--real-model"):
        pytest.skip("Pass --real-model to run end-to-end API tests")

    from api.config import get_settings
    get_settings.cache_clear()

    real_detector = AIImageDetector()

    import api.server

    with patch("api.server.AIImageDetector", return_value=real_detector):
        importlib.reload(api.server)
        api.server.detector = real_detector
        api.server.cache = ImageCache(max_size=10, ttl=300)
        api.server.json_logger = JSONLogger(log_dir=tempfile.mkdtemp())
        api.server.rate_limiter = TokenBucketRateLimiter(requests_per_window=30, window_seconds=60)

        yield TestClient(api.server.app, raise_server_exceptions=True)


class TestE2EAnalyze:
    def test_analyze_returns_200(self, real_api_client):
        resp = real_api_client.post("/analyze", json={
            "image_base64": _b64_image(),
            "source_url": "https://example.com",
        })
        assert resp.status_code == 200

    def test_analyze_response_shape(self, real_api_client):
        data = real_api_client.post("/analyze", json={
            "image_base64": _b64_image(),
            "source_url": "https://example.com",
        }).json()
        assert set(data.keys()) >= {
            "is_ai", "confidence", "verdict",
            "fake_probability", "real_probability",
            "image_hash", "processing_time_ms", "cached",
        }

    def test_analyze_verdict_is_valid(self, real_api_client):
        data = real_api_client.post("/analyze", json={
            "image_base64": _b64_image(),
            "source_url": "https://example.com",
        }).json()
        assert data["verdict"] in VALID_VERDICTS

    def test_probabilities_sum_to_one(self, real_api_client):
        data = real_api_client.post("/analyze", json={
            "image_base64": _b64_image(),
            "source_url": "https://example.com",
        }).json()
        assert abs(data["fake_probability"] + data["real_probability"] - 1.0) < 0.01

    def test_confidence_matches_verdict(self, real_api_client):
        data = real_api_client.post("/analyze", json={
            "image_base64": _b64_image(),
            "source_url": "https://example.com",
        }).json()
        if data["verdict"] == "Likely AI":
            assert data["confidence"] == pytest.approx(data["fake_probability"])
            assert data["confidence"] > 0.6
        elif data["verdict"] == "Likely Real":
            assert data["confidence"] == pytest.approx(data["real_probability"])
            assert data["confidence"] > 0.6
        else:
            assert data["verdict"] == "Uncertain"
            assert data["confidence"] <= 0.6

    def test_second_request_is_cached(self, real_api_client):
        b64 = _b64_image(color=(200, 100, 50))
        # Send twice — second must always be a cache hit regardless of first
        real_api_client.post("/analyze", json={"image_base64": b64, "source_url": "https://example.com"})
        r2 = real_api_client.post("/analyze", json={"image_base64": b64, "source_url": "https://example.com"})
        assert r2.status_code == 200
        assert r2.json()["cached"] is True

    def test_invalid_base64_returns_400(self, real_api_client):
        resp = real_api_client.post("/analyze", json={
            "image_base64": "not-valid-base64!!!",
            "source_url": "https://example.com",
        })
        assert resp.status_code == 400
