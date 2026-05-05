"""API integration tests."""

import base64
import io
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image


@pytest.fixture
def mock_env_no_auth(monkeypatch):
    """Disable API key auth for tests."""
    monkeypatch.setenv("API_KEY", "")
    monkeypatch.setenv("CORS_ORIGINS", "*")


@pytest.fixture
def mock_env_with_auth(monkeypatch):
    """Enable API key auth for tests."""
    monkeypatch.setenv("API_KEY", "test-secret-key")
    monkeypatch.setenv("CORS_ORIGINS", "*")


def _make_base64_image(width=224, height=224, color=(128, 128, 128)):
    """Create a base64-encoded test image."""
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _create_app(monkeypatch):
    """Create a fresh app with mocked detector."""
    # Clear settings cache
    from api.config import get_settings
    get_settings.cache_clear()

    mock_result = {
        "is_ai": True,
        "confidence": 0.85,
        "verdict": "Likely AI",
        "full_analysis": "AI: 85.0%, Human: 15.0%",
        "fake_probability": 0.85,
        "real_probability": 0.15,
        "processing_time_ms": 10.0,
    }

    mock_detector = MagicMock()
    mock_detector.analyze_image.return_value = mock_result
    mock_detector.get_model_info.return_value = {"name": "test", "device": "cpu", "accuracy": "94.2%"}
    mock_detector.device = "cpu"

    with patch("api.server.AIImageDetector", return_value=mock_detector):
        with patch("api.server.asyncio") as mock_asyncio:
            # Make to_thread just call the function directly
            mock_asyncio.to_thread = AsyncMock(side_effect=lambda fn, *a, **kw: fn(*a, **kw))
            mock_asyncio.gather = AsyncMock(side_effect=lambda *coros: [])

            # Re-import to get fresh module state
            import importlib

            import api.server
            importlib.reload(api.server)

            # Manually initialize globals
            api.server.detector = mock_detector
            import tempfile

            from api.rate_limiter import TokenBucketRateLimiter
            from modules.image_cache import ImageCache
            from modules.json_logger import JSONLogger

            api.server.cache = ImageCache(max_size=10, ttl=300)
            tmpdir = tempfile.mkdtemp()
            api.server.json_logger = JSONLogger(log_dir=tmpdir)
            api.server.rate_limiter = TokenBucketRateLimiter(requests_per_window=30, window_seconds=60)

            client = TestClient(api.server.app, raise_server_exceptions=False)
            return client


class TestHealthEndpoint:
    def test_health_returns_ok(self, mock_env_no_auth, monkeypatch):
        client = _create_app(monkeypatch)
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["model_loaded"] is True

    def test_health_no_auth_required(self, mock_env_with_auth, monkeypatch):
        client = _create_app(monkeypatch)
        resp = client.get("/health")
        assert resp.status_code == 200


class TestStatsEndpoint:
    def test_stats_returns_ok(self, mock_env_no_auth, monkeypatch):
        client = _create_app(monkeypatch)
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_analyses" in data
        assert "cache_hit_rate" in data


class TestAnalyzeEndpoint:
    def test_analyze_valid_image(self, mock_env_no_auth, monkeypatch):
        client = _create_app(monkeypatch)
        b64 = _make_base64_image()
        resp = client.post("/analyze", json={
            "image_base64": b64,
            "source_url": "https://example.com",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "is_ai" in data
        assert "confidence" in data
        assert "verdict" in data

    def test_analyze_invalid_base64(self, mock_env_no_auth, monkeypatch):
        client = _create_app(monkeypatch)
        resp = client.post("/analyze", json={
            "image_base64": "not-valid-base64!!!",
            "source_url": "https://example.com",
        })
        assert resp.status_code == 400

    def test_analyze_missing_fields(self, mock_env_no_auth, monkeypatch):
        client = _create_app(monkeypatch)
        resp = client.post("/analyze", json={})
        assert resp.status_code == 422

    def test_analyze_requires_auth_when_configured(self, mock_env_with_auth, monkeypatch):
        client = _create_app(monkeypatch)
        b64 = _make_base64_image()
        resp = client.post("/analyze", json={
            "image_base64": b64,
            "source_url": "https://example.com",
        })
        assert resp.status_code == 401

    def test_analyze_with_valid_api_key(self, mock_env_with_auth, monkeypatch):
        client = _create_app(monkeypatch)
        b64 = _make_base64_image()
        resp = client.post("/analyze",
            json={
                "image_base64": b64,
                "source_url": "https://example.com",
            },
            headers={"X-API-Key": "test-secret-key"},
        )
        assert resp.status_code == 200

    def test_analyze_with_wrong_api_key(self, mock_env_with_auth, monkeypatch):
        client = _create_app(monkeypatch)
        b64 = _make_base64_image()
        resp = client.post("/analyze",
            json={
                "image_base64": b64,
                "source_url": "https://example.com",
            },
            headers={"X-API-Key": "wrong-key"},
        )
        assert resp.status_code == 401


class TestRateLimiting:
    def test_rate_limit_returns_429(self, mock_env_no_auth, monkeypatch):
        client = _create_app(monkeypatch)
        b64 = _make_base64_image()

        # Exhaust rate limit
        import api.server
        from api.rate_limiter import TokenBucketRateLimiter
        api.server.rate_limiter = TokenBucketRateLimiter(requests_per_window=1, window_seconds=60)

        # First request succeeds
        resp = client.post("/analyze", json={
            "image_base64": b64,
            "source_url": "https://example.com",
        })
        assert resp.status_code == 200

        # Second request rate limited
        resp = client.post("/analyze", json={
            "image_base64": b64,
            "source_url": "https://example.com",
        })
        assert resp.status_code == 429
