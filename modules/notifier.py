"""Desktop notifications and alert sounds for AI image detection."""
import threading

try:
    import winsound
    _HAS_WINSOUND = True
except ImportError:
    _HAS_WINSOUND = False

try:
    from plyer import notification as _plyer
    _HAS_PLYER = True
except ImportError:
    _HAS_PLYER = False


class Notifier:
    """Sends desktop toast notifications and plays alert sounds."""

    _APP_NAME = "AI Image Detector"

    def ai_detected(self, verdict: str, confidence: float) -> None:
        """Notify that an AI-generated image was detected (with alert sound)."""
        self._play_alert()
        self._notify("AI Image Detected", f"{verdict} — {confidence * 100:.0f}% confidence", timeout=5)

    def info(self, title: str, message: str) -> None:
        """Show an informational notification without sound."""
        self._notify(title, message, timeout=6)

    def _notify(self, title: str, message: str, timeout: int = 5) -> None:
        if _HAS_PLYER:
            try:
                _plyer.notify(app_name=self._APP_NAME, title=title, message=message, timeout=timeout)
                return
            except Exception:
                pass
        print(f"[{title}] {message}")

    def _play_alert(self) -> None:
        if not _HAS_WINSOUND:
            return

        def _play():
            try:
                winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
            except Exception:
                try:
                    winsound.Beep(800, 200)
                    winsound.Beep(600, 200)
                    winsound.Beep(400, 300)
                except Exception:
                    pass

        threading.Thread(target=_play, daemon=True).start()
