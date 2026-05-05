
import mss
from PIL import Image


class ScreenCapture:
    """Captures screenshots of the screen"""

    def __init__(self):
        # Don't store mss instance - create fresh one each capture for thread safety
        pass

    def capture_screen(self, monitor_num=1):
        """
        Capture the specified monitor.

        Args:
            monitor_num: Monitor number (1 = primary monitor)

        Returns:
            PIL.Image: Screenshot as PIL Image
        """
        # Create new mss instance for each capture (thread-safe)
        with mss.mss() as sct:
            monitor = sct.monitors[monitor_num]
            screenshot = sct.grab(monitor)

            # Convert to PIL Image
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            return img

    def capture_region(self, left, top, width, height):
        """
        Capture a specific region of the screen.

        Args:
            left, top: Top-left corner coordinates
            width, height: Size of region

        Returns:
            PIL.Image: Screenshot as PIL Image
        """
        with mss.mss() as sct:
            region = {"left": left, "top": top, "width": width, "height": height}
            screenshot = sct.grab(region)

            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
            return img

    def get_screen_size(self, monitor_num=1):
        """Get the size of the specified monitor"""
        with mss.mss() as sct:
            monitor = sct.monitors[monitor_num]
            return monitor["width"], monitor["height"]
