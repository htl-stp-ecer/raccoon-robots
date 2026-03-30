
import threading
import time

from libstp import GenericRobot, RobotService
from libstp.step.calibration.store import CalibrationStore

from src.hardware.usb_camera import USBCamera

# Default HSV ranges — used when no calibration data exists.
DEFAULT_BLUE_HSV_RANGES = [((85, 25, 25), (135, 255, 255))]
DEFAULT_PINK_HSV_RANGES = [((140, 25, 25), (180, 255, 255)),
                            ((0, 25, 25), (10, 255, 255))]  # wrap around red

ANALYSIS_FRAMES = 5
PRESENCE_THRESHOLD = 0.3


DEFAULT_MIN_AREA = 300


def _load_calibration() -> tuple[list, list, int] | None:
    """Try loading HSV ranges + min_area from racoon.calibration.yml."""
    store = CalibrationStore()
    data = store.load("color-detection", "default")
    if data is None:
        return None
    try:
        blue = [(tuple(lo), tuple(hi)) for lo, hi in data.get("blue_ranges", [])]
        pink = [(tuple(lo), tuple(hi)) for lo, hi in data.get("pink_ranges", [])]
        min_area = int(data.get("min_area", DEFAULT_MIN_AREA))
        return blue, pink, min_area
    except (TypeError, ValueError):
        return None


class ColorDetectionService(RobotService):
    """Continuously detect drum color (blue/pink) via USB camera.

    A background thread analyzes frames as fast as it can.
    The latest detected color is always available. Consuming it clears
    the cached value so stale data is never reused.

    HSV ranges are loaded from calibration YAML if available,
    otherwise falls back to hardcoded defaults.
    """

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)

        calibrated = _load_calibration()
        if calibrated and calibrated[0] and calibrated[1]:
            blue_ranges, pink_ranges, min_area = calibrated
            self.info(
                f"Loaded calibrated color ranges from racoon.calibration.yml "
                f"(min_area={min_area})",
            )
        else:
            blue_ranges = DEFAULT_BLUE_HSV_RANGES
            pink_ranges = DEFAULT_PINK_HSV_RANGES
            min_area = DEFAULT_MIN_AREA
            self.info("Using default color ranges (no calibration found)")

        self._camera = USBCamera(
            camera_index="/dev/video0",
            resolution=(320, 240),
            buffer_size=30,
            capture_fps=15,
            save_frames=False,
            frames_dir="frames",
            get_time=lambda: time.monotonic() - self._camera_start_time,
        )
        self._camera.add_color("blue", hsv_ranges=blue_ranges,
                               min_area=min_area, min_dimension=10)
        self._camera.add_color("pink", hsv_ranges=pink_ranges,
                               min_area=min_area, min_dimension=10)

        self._camera_start_time: float = 0.0
        self._lock = threading.Lock()
        self._latest_color: str | None = None
        self._detection_thread: threading.Thread | None = None
        self._running = False

    def start_camera(self) -> None:
        """Start background capture and continuous detection."""
        self._camera_start_time = time.monotonic()
        self._camera.start()
        self._running = True
        self._detection_thread = threading.Thread(
            target=self._detection_loop, daemon=True,
        )
        self._detection_thread.start()
        self.info("Camera started — continuous color detection running")

    def stop_camera(self) -> None:
        """Stop detection and release camera."""
        self._running = False
        if self._detection_thread is not None:
            self._detection_thread.join(timeout=2.0)
            self._detection_thread = None
        self._camera.stop()
        self.info("Camera stopped")

    def _detection_loop(self) -> None:
        """Continuously analyze frames and cache the detected color."""
        import os

        detect_count = 0
        log_window_start = time.monotonic()
        last_frame_id = 0

        while self._running:
            current_frame_id = self._camera.total_frames
            if current_frame_id < ANALYSIS_FRAMES or current_frame_id == last_frame_id:
                time.sleep(0.02)
                continue
            last_frame_id = current_frame_id

            t0 = time.monotonic()
            result = self._camera.analyze(
                last_n_frames=ANALYSIS_FRAMES,
                presence_threshold=PRESENCE_THRESHOLD,
            )
            analysis_ms = (time.monotonic() - t0) * 1000
            detect_count += 1

            blue = result.get("blue")
            pink = result.get("pink")
            blue_present = blue is not None and blue.present
            pink_present = pink is not None and pink.present

            if blue_present and pink_present:
                color = "blue" if blue.confidence >= pink.confidence else "pink"
            elif blue_present:
                color = "blue"
            elif pink_present:
                color = "pink"
            else:
                color = None

            if color is not None:
                with self._lock:
                    self._latest_color = color

            # Log performance every 5 seconds
            log_elapsed = time.monotonic() - log_window_start
            if log_elapsed >= 5.0:
                detect_fps = detect_count / log_elapsed
                try:
                    load1, load5, load15 = os.getloadavg()
                    cpu_str = f"load={load1:.1f}/{load5:.1f}/{load15:.1f}"
                except OSError:
                    cpu_str = "load=N/A"
                self.info(
                    f"Detection: {detect_fps:.1f} Hz, "
                    f"last analysis={analysis_ms:.0f}ms, "
                    f"{cpu_str}"
                )
                detect_count = 0
                log_window_start = time.monotonic()

    def reset(self) -> None:
        """Clear cached detection. Call when a new drum cycle starts."""
        with self._lock:
            self._latest_color = None

    @property
    def peek_color(self) -> str | None:
        """Read the current detected color without consuming it."""
        with self._lock:
            return self._latest_color

    async def detect_color(self) -> str:
        """Return the last detected color and clear it.

        Logs an error if no color was detected.
        """
        with self._lock:
            color = self._latest_color
            self._latest_color = None

        if color is None:
            self.error("No color detected by camera — could not determine drum color")
            return "blue"

        self.info(f"Detected color: {color}")
        return color

    def apply_calibration(
        self,
        blue_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]],
        pink_ranges: list[tuple[tuple[int, ...], tuple[int, ...]]],
        min_area: int = DEFAULT_MIN_AREA,
    ) -> None:
        """Hot-swap HSV ranges and min_area on the running camera."""
        if blue_ranges:
            self._camera.remove_color("blue")
            self._camera.add_color("blue", hsv_ranges=blue_ranges,
                                   min_area=min_area, min_dimension=10)
        if pink_ranges:
            self._camera.remove_color("pink")
            self._camera.add_color("pink", hsv_ranges=pink_ranges,
                                   min_area=min_area, min_dimension=10)
        self.info(f"Color calibration applied at runtime (min_area={min_area})")
