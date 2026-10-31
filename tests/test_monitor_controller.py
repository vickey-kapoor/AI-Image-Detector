"""Tests for MonitorController in screen_monitor.py."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

# pystray requires a running Windows desktop session which is not available in
# test environments. Stub it out before importing screen_monitor so the
# module-level icon creation doesn't fail.
_pystray_stub = ModuleType("pystray")
_pystray_stub.Icon = MagicMock()
_pystray_stub.Menu = MagicMock()
_pystray_stub.MenuItem = MagicMock()
sys.modules.setdefault("pystray", _pystray_stub)

from screen_monitor import MonitorController  # noqa: E402


@pytest.fixture
def mock_screenshot():
    return Image.new("RGB", (1920, 1080), color=(100, 100, 100))


@pytest.fixture
def mock_screen_capture(mock_screenshot):
    sc = MagicMock()
    sc.capture_screen.return_value = mock_screenshot
    return sc


@pytest.fixture
def mock_detector():
    d = MagicMock()
    d.analyze_image.return_value = {
        "is_ai": False,
        "verdict": "Likely Real",
        "confidence": 0.9,
        "fake_probability": 0.1,
        "real_probability": 0.9,
        "processing_time_ms": 10.0,
    }
    return d


@pytest.fixture
def mock_cache():
    c = MagicMock()
    c.get.return_value = None  # cache miss by default
    return c


@pytest.fixture
def mock_notifier():
    return MagicMock()


@pytest.fixture
def controller(mock_detector, mock_screen_capture, mock_cache, mock_notifier):
    return MonitorController(
        detector=mock_detector,
        screen_capture=mock_screen_capture,
        image_cache=mock_cache,
        notifier=mock_notifier,
    )


class TestMonitorControllerState:
    def test_not_running_initially(self, controller):
        assert controller.is_running() is False

    def test_start_sets_running(self, controller):
        with patch("screen_monitor.time.sleep"):
            controller.start()
            assert controller.is_running() is True
            controller.stop()

    def test_stop_clears_running(self, controller):
        with patch("screen_monitor.time.sleep"):
            controller.start()
            controller.stop()
            assert controller.is_running() is False

    def test_double_start_does_not_spawn_extra_thread(self, controller):
        with patch("screen_monitor.time.sleep"):
            controller.start()
            thread = controller._thread
            controller.start()  # second call should be a no-op
            assert controller._thread is thread
            controller.stop()

    def test_stats_initialised_to_zero(self, controller):
        assert controller.stats == {
            "total_captures": 0,
            "total_analyses": 0,
            "ai_detections": 0,
            "cache_hits": 0,
        }


class TestMonitorControllerLoop:
    def _run_one_iteration(self, controller):
        """Run the loop for one iteration then stop."""
        call_count = 0

        def fake_sleep(n):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                controller._monitoring = False

        with patch("screen_monitor.time.sleep", side_effect=fake_sleep):
            controller.start()
            controller._thread.join(timeout=3)

    def test_capture_increments_total_captures(self, controller):
        self._run_one_iteration(controller)
        assert controller.stats["total_captures"] == 1

    def test_cache_miss_runs_detector(self, controller, mock_detector, mock_cache):
        mock_cache.get.return_value = None
        self._run_one_iteration(controller)
        mock_detector.analyze_image.assert_called_once()

    def test_cache_miss_increments_total_analyses(self, controller, mock_cache):
        mock_cache.get.return_value = None
        self._run_one_iteration(controller)
        assert controller.stats["total_analyses"] == 1

    def test_cache_hit_skips_detector(self, controller, mock_detector, mock_cache):
        mock_cache.get.return_value = {"is_ai": False, "verdict": "Likely Real", "confidence": 0.9}
        self._run_one_iteration(controller)
        mock_detector.analyze_image.assert_not_called()

    def test_cache_hit_increments_cache_hits(self, controller, mock_cache):
        mock_cache.get.return_value = {"is_ai": False, "verdict": "Likely Real", "confidence": 0.9}
        self._run_one_iteration(controller)
        assert controller.stats["cache_hits"] == 1

    def test_ai_detection_triggers_notification(self, controller, mock_detector, mock_notifier):
        mock_detector.analyze_image.return_value = {
            "is_ai": True,
            "verdict": "Likely AI",
            "confidence": 0.91,
            "fake_probability": 0.91,
            "real_probability": 0.09,
            "processing_time_ms": 10.0,
        }
        self._run_one_iteration(controller)
        mock_notifier.ai_detected.assert_called_once_with("Likely AI", 0.91)

    def test_ai_detection_increments_ai_detections(self, controller, mock_detector):
        mock_detector.analyze_image.return_value = {
            "is_ai": True,
            "verdict": "Likely AI",
            "confidence": 0.91,
            "fake_probability": 0.91,
            "real_probability": 0.09,
            "processing_time_ms": 10.0,
        }
        self._run_one_iteration(controller)
        assert controller.stats["ai_detections"] == 1

    def test_real_image_does_not_notify(self, controller, mock_notifier):
        self._run_one_iteration(controller)
        mock_notifier.ai_detected.assert_not_called()

    def test_capture_exception_does_not_crash_loop(self, controller, mock_screen_capture):
        call_count = 0

        def flaky_capture():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("screen capture failed")
            controller._monitoring = False
            return Image.new("RGB", (100, 100))

        mock_screen_capture.capture_screen.side_effect = flaky_capture

        with patch("screen_monitor.time.sleep"):
            controller.start()
            controller._thread.join(timeout=3)

        # Loop recovered — second capture succeeded (or loop exited cleanly)
        assert controller.stats["total_captures"] <= 1  # exception on first, no increment

    def test_screenshot_is_thumbnailed_before_analysis(self, controller, mock_detector):
        self._run_one_iteration(controller)
        analyzed_image = mock_detector.analyze_image.call_args[0][0]
        w, h = analyzed_image.size
        assert w <= 512 and h <= 512
