import threading
import tkinter as tk
import winsound


class OverlayWindow:
    """Full-screen overlay to show AI detection results"""

    def __init__(self, root):
        self.root = root
        self.overlay = None
        self.is_showing = False
        self.auto_hide_job = None

    def show_result(self, is_ai, verdict="Unknown", confidence=0, duration=2500):
        """
        Show the detection result - X (AI), ? (Uncertain), or checkmark (Real).

        Args:
            is_ai: True if AI-generated, False if real
            verdict: The verdict string ('Likely AI', 'Uncertain', 'Likely Real')
            confidence: Confidence percentage (0-1)
            duration: How long to show in milliseconds
        """
        if verdict == 'Likely AI' or verdict == 'AI-Generated':
            self.show_alert(duration=duration, verdict=verdict, confidence=confidence)
        elif verdict == 'Uncertain':
            self.show_uncertain(duration=duration, confidence=confidence)
        else:
            self.show_real(duration=duration, verdict=verdict, confidence=confidence)

    def show_uncertain(self, duration=2500, confidence=0):
        """
        Show yellow question mark for uncertain results.
        """
        self._hide_current()
        self.is_showing = True

        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-topmost', True)
        self.overlay.attributes('-alpha', 0.9)
        self.overlay.overrideredirect(True)

        screen_width = self.overlay.winfo_screenwidth()
        overlay_size = 150
        padding = 20
        self.overlay.geometry(f"{overlay_size}x{overlay_size + 50}+{screen_width - overlay_size - padding}+{padding}")

        # Yellow/orange border
        frame = tk.Frame(self.overlay, bg="#f39c12", padx=3, pady=3)
        frame.pack(fill=tk.BOTH, expand=True)

        inner_frame = tk.Frame(frame, bg="white")
        inner_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for question mark
        canvas_size = 100
        canvas = tk.Canvas(inner_frame, width=canvas_size, height=canvas_size, bg="white", highlightthickness=0)
        canvas.pack(pady=(15, 5))

        # Draw yellow/orange circle
        padding_circle = 5
        canvas.create_oval(
            padding_circle, padding_circle,
            canvas_size - padding_circle, canvas_size - padding_circle,
            fill="#f39c12", outline="#d68910", width=3
        )

        # Draw white question mark
        canvas.create_text(
            canvas_size // 2, canvas_size // 2,
            text="?",
            font=("Arial", 48, "bold"),
            fill="white"
        )

        # Label
        label = tk.Label(inner_frame, text="UNCERTAIN", font=("Arial", 11, "bold"), bg="white", fg="#f39c12")
        label.pack()

        conf_label = tk.Label(inner_frame, text=f"{confidence*100:.0f}% confident", font=("Arial", 9), bg="white", fg="#7f8c8d")
        conf_label.pack(pady=(0, 10))

        self.auto_hide_job = self.overlay.after(duration, self.hide_alert)

    def show_real(self, duration=2500, verdict="Real", confidence=0):
        """
        Show the green checkmark for real photographs.

        Args:
            duration: How long to show overlay in milliseconds
        """
        self._hide_current()
        self.is_showing = True

        # Create overlay window
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-topmost', True)
        self.overlay.attributes('-alpha', 0.9)
        self.overlay.overrideredirect(True)

        # Position in top-right corner
        screen_width = self.overlay.winfo_screenwidth()
        overlay_size = 150
        padding = 20
        self.overlay.geometry(f"{overlay_size}x{overlay_size + 50}+{screen_width - overlay_size - padding}+{padding}")

        # Main frame with green border
        frame = tk.Frame(self.overlay, bg="#1e8449", padx=3, pady=3)
        frame.pack(fill=tk.BOTH, expand=True)

        inner_frame = tk.Frame(frame, bg="white")
        inner_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for checkmark symbol
        canvas_size = 100
        canvas = tk.Canvas(
            inner_frame,
            width=canvas_size,
            height=canvas_size,
            bg="white",
            highlightthickness=0
        )
        canvas.pack(pady=(15, 5))

        # Draw green circle
        padding_circle = 5
        canvas.create_oval(
            padding_circle, padding_circle,
            canvas_size - padding_circle, canvas_size - padding_circle,
            fill="#27ae60", outline="#1e8449", width=3
        )

        # Draw white checkmark
        canvas.create_line(25, 50, 42, 70, fill="white", width=8, capstyle="round")
        canvas.create_line(42, 70, 75, 30, fill="white", width=8, capstyle="round")

        # Label
        label = tk.Label(
            inner_frame,
            text="REAL IMAGE",
            font=("Arial", 11, "bold"),
            bg="white",
            fg="#27ae60"
        )
        label.pack()

        # Confidence
        conf_label = tk.Label(
            inner_frame,
            text=f"{confidence*100:.0f}% confident",
            font=("Arial", 9),
            bg="white",
            fg="#7f8c8d"
        )
        conf_label.pack(pady=(0, 10))

        # Auto-hide
        self.auto_hide_job = self.overlay.after(duration, self.hide_alert)

    def _hide_current(self):
        """Hide current overlay if showing"""
        if self.is_showing:
            self.hide_alert()

    def show_alert(self, duration=3000, verdict="AI-Generated", confidence=0):
        """
        Show the X symbol alert overlay with sound.

        Args:
            duration: How long to show overlay in milliseconds
            verdict: The verdict string
            confidence: Confidence (0-1)
        """
        self._hide_current()
        self.is_showing = True

        # Play alert sound in background
        self._play_alert_sound()

        # Create overlay window
        self.overlay = tk.Toplevel(self.root)
        self.overlay.attributes('-topmost', True)
        self.overlay.attributes('-alpha', 0.9)
        self.overlay.overrideredirect(True)  # No window decorations

        # Position in top-right corner of screen
        screen_width = self.overlay.winfo_screenwidth()
        overlay_size = 150
        padding = 20
        self.overlay.geometry(f"{overlay_size}x{overlay_size + 55}+{screen_width - overlay_size - padding}+{padding}")

        # Main frame with red border
        frame = tk.Frame(self.overlay, bg="#c0392b", padx=3, pady=3)
        frame.pack(fill=tk.BOTH, expand=True)

        inner_frame = tk.Frame(frame, bg="white")
        inner_frame.pack(fill=tk.BOTH, expand=True)

        # Canvas for X symbol
        canvas_size = 100
        canvas = tk.Canvas(
            inner_frame,
            width=canvas_size,
            height=canvas_size,
            bg="white",
            highlightthickness=0
        )
        canvas.pack(pady=(15, 5))

        # Draw red circle
        padding = 5
        canvas.create_oval(
            padding, padding,
            canvas_size - padding, canvas_size - padding,
            fill="#e74c3c", outline="#c0392b", width=3
        )

        # Draw white X
        line_padding = 25
        line_width = 8
        canvas.create_line(
            line_padding, line_padding,
            canvas_size - line_padding, canvas_size - line_padding,
            fill="white", width=line_width, capstyle="round"
        )
        canvas.create_line(
            canvas_size - line_padding, line_padding,
            line_padding, canvas_size - line_padding,
            fill="white", width=line_width, capstyle="round"
        )

        # Warning text
        label = tk.Label(
            inner_frame,
            text=verdict.upper(),
            font=("Arial", 11, "bold"),
            bg="white",
            fg="#e74c3c"
        )
        label.pack()

        # Confidence
        conf_label = tk.Label(
            inner_frame,
            text=f"{confidence*100:.0f}% confident",
            font=("Arial", 9),
            bg="white",
            fg="#7f8c8d"
        )
        conf_label.pack(pady=(0, 10))

        # Auto-hide after duration
        self.auto_hide_job = self.overlay.after(duration, self.hide_alert)

    def _play_alert_sound(self):
        """Play alert sound in a separate thread"""
        def _play():
            try:
                # Try to play system exclamation sound (non-blocking)
                try:
                    winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
                except Exception:
                    pass  # System sound not available, continue with beeps

                # Play descending beeps as the main alert
                winsound.Beep(800, 200)
                winsound.Beep(600, 200)
                winsound.Beep(400, 300)
            except Exception as e:
                # Beep failed - likely no audio device or running in restricted environment
                print(f"Sound error: {e}")

        threading.Thread(target=_play, daemon=True).start()

    def hide_alert(self):
        """Hide the overlay"""
        if self.auto_hide_job:
            try:
                self.overlay.after_cancel(self.auto_hide_job)
            except Exception:
                pass
            self.auto_hide_job = None

        if self.overlay:
            try:
                self.overlay.destroy()
            except Exception:
                pass
            self.overlay = None

        self.is_showing = False

    def destroy(self):
        """Clean up"""
        self.hide_alert()
