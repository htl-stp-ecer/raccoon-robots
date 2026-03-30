
import asyncio
import threading

from libstp import GenericRobot, RobotService

from src.hardware.usb_camera import USBCamera

# HSV ranges — tune these under competition lighting
BLUE_HSV_RANGES = [((100, 80, 100), (130, 255, 255))]
PINK_HSV_RANGES = [((150, 80, 100), (170, 255, 255)),
                    ((170, 80, 100), (180, 255, 255))]

ANALYSIS_FRAMES = 5
PRESENCE_THRESHOLD = 0.5


class ColorDetectionService(RobotService):
    """Detect drum color (blue/pink) via USB camera with scheduled analysis."""

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)
        self._camera = USBCamera(
            camera_index=0,
            resolution=(320, 240),
            buffer_size=30,
            capture_fps=15,
        )
        self._camera.add_color("blue", hsv_ranges=BLUE_HSV_RANGES)
        self._camera.add_color("pink", hsv_ranges=PINK_HSV_RANGES)

        self._pending_color: str | None = None
        self._result_ready = asyncio.Event()
        self._analysis_lock = threading.Lock()

    def start_camera(self) -> None:
        """Start the background capture thread."""
        self._camera.start()
        self.info("Camera started — capturing frames in background")

    def stop_camera(self) -> None:
        """Stop capture and release camera."""
        self._camera.stop()
        self.info("Camera stopped")

    def schedule_detection(self) -> None:
        """Kick off frame analysis in a background thread.

        Call this ~0.3 s before detect_color() is needed.
        The analysis runs on a worker thread so it doesn't block the event loop.
        """
        self._result_ready.clear()
        self._pending_color = None

        def _analyze() -> None:
            result = self._camera.analyze(
                last_n_frames=ANALYSIS_FRAMES,
                presence_threshold=PRESENCE_THRESHOLD,
            )

            blue = result.get("blue")
            pink = result.get("pink")
            blue_present = blue is not None and blue.present
            pink_present = pink is not None and pink.present

            if blue_present and pink_present:
                # Both detected — pick the one with higher confidence
                color = "blue" if blue.confidence >= pink.confidence else "pink"
            elif blue_present:
                color = "blue"
            elif pink_present:
                color = "pink"
            else:
                color = "blue"  # fallback
                self.warn("No color detected — defaulting to blue")

            with self._analysis_lock:
                self._pending_color = color

            # Thread-safe way to set the asyncio event from a worker thread
            loop = asyncio._get_running_loop()
            if loop is not None:
                loop.call_soon_threadsafe(self._result_ready.set)
            else:
                self._result_ready.set()

        threading.Thread(target=_analyze, daemon=True).start()
        self.info("Color analysis scheduled")

    async def detect_color(self) -> str:
        """Return 'blue' or 'pink' for the current drum.

        Waits for the result from a prior schedule_detection() call.
        If no analysis was scheduled, runs one synchronously.
        """
        if self._pending_color is None and not self._result_ready.is_set():
            self.warn("detect_color called without schedule_detection — analyzing now")
            self.schedule_detection()

        try:
            await asyncio.wait_for(self._result_ready.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            self.warn("Analysis timed out — defaulting to blue")
            return "blue"

        color = self._pending_color or "blue"
        self.info(f"Detected color: {color}")
        return color
