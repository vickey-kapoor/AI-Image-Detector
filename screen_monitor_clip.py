"""
AI Image Detection - System Tray Monitor
Runs silently in the background; notifies when AI-generated images are detected.
"""
import threading
import time

import pystray
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont

from modules.ai_detector import AIImageDetector
from modules.image_cache import ImageCache
from modules.notifier import Notifier
from modules.screen_capture import ScreenCapture


def _make_tray_icon(color: str) -> Image.Image:
    size = 64
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, size - 4, size - 4], fill=color)
    try:
        font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 22)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "AI", font=font)
    text_w, text_h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - text_w) // 2, (size - text_h) // 2 - 2), "AI", fill="white", font=font)
    return img


_ICON_IDLE = _make_tray_icon("#607d8b")    # grey-blue = stopped
_ICON_ACTIVE = _make_tray_icon("#27ae60")  # green = monitoring


class MonitorController:
    """Captures and analyses the screen on a background thread."""

    _INTERVAL = 3  # seconds between captures

    def __init__(self, detector, screen_capture, image_cache, notifier):
        self.detector = detector
        self.screen_capture = screen_capture
        self.image_cache = image_cache
        self.notifier = notifier
        self._monitoring = False
        self._thread = None
        self.stats = {"total_captures": 0, "total_analyses": 0, "ai_detections": 0, "cache_hits": 0}

    def start(self):
        if self._monitoring:
            return
        self._monitoring = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._monitoring = False
        if self._thread:
            self._thread.join(timeout=5)

    def is_running(self) -> bool:
        return self._monitoring

    def _loop(self):
        while self._monitoring:
            try:
                screenshot = self.screen_capture.capture_screen()
                self.stats["total_captures"] += 1

                thumb = screenshot.copy()
                thumb.thumbnail((512, 512), Image.Resampling.LANCZOS)

                if self.image_cache.get(thumb):
                    self.stats["cache_hits"] += 1
                    time.sleep(self._INTERVAL)
                    continue

                result = self.detector.analyze_image(thumb)
                self.image_cache.set(thumb, result)
                self.stats["total_analyses"] += 1

                if result.get("is_ai"):
                    self.stats["ai_detections"] += 1
                    self.notifier.ai_detected(result["verdict"], result["confidence"])

            except Exception as e:
                print(f"Monitor error: {e}")

            time.sleep(self._INTERVAL)


class SystemTrayApp:
    """System tray application wrapping the monitor controller."""

    def __init__(self):
        load_dotenv()
        print("Initialising AI Image Detector...")

        detector = AIImageDetector()
        self.monitor = MonitorController(
            detector=detector,
            screen_capture=ScreenCapture(),
            image_cache=ImageCache(max_size=50, ttl=300),
            notifier=Notifier(),
        )
        self.icon = pystray.Icon(
            "AI Image Detector",
            icon=_ICON_IDLE,
            title="AI Image Detector — Stopped",
            menu=self._build_menu(),
        )

    def _build_menu(self) -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(
                text=lambda _: "Stop Monitoring" if self.monitor.is_running() else "Start Monitoring",
                action=self._toggle,
                default=True,
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show Stats", self._show_stats),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", self._quit),
        )

    def _toggle(self, icon, item):
        if self.monitor.is_running():
            self.monitor.stop()
            icon.icon = _ICON_IDLE
            icon.title = "AI Image Detector — Stopped"
        else:
            self.monitor.start()
            icon.icon = _ICON_ACTIVE
            icon.title = "AI Image Detector — Monitoring"

    def _show_stats(self, icon, item):
        s = self.monitor.stats
        total = s["total_analyses"]
        hits = s["cache_hits"]
        rate = hits / (total + hits) * 100 if (total + hits) > 0 else 0.0
        Notifier().info(
            "Session Stats",
            f"Scans: {total}  |  AI detected: {s['ai_detections']}\n"
            f"Cache hits: {hits}  |  Hit rate: {rate:.0f}%",
        )

    def _quit(self, icon, item):
        self.monitor.stop()
        icon.stop()

    def run(self):
        print("Running in system tray. Right-click the tray icon to start monitoring or quit.")
        self.icon.run()


def main():
    SystemTrayApp().run()


if __name__ == "__main__":
    main()
