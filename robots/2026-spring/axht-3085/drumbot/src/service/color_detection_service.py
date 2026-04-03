import threading
import time

from libstp import GenericRobot, RobotService

from src.hardware.usb_camera import USBCamera

ANALYSIS_FRAMES = 1
PRESENCE_THRESHOLD = 0.9
DEFAULT_MIN_AREA = 500


class ColorDetectionService(RobotService):
    """Continuously detect drum color (blue/pink) via USB camera.

    Calibration is always injected via apply_calibration() and called by
    ColorCalibrationStep._apply() whether running live or with --no-calibrate.
    No YAML loading here, no defaults, no fallbacks.
    """

    def __init__(self, robot: "GenericRobot") -> None:
        super().__init__(robot)

        self._camera = USBCamera(
            camera_index="/dev/video0",
            resolution=(160, 120),
            buffer_size=10,
            capture_fps=30,
            save_frames=False,
            frames_dir="frames",
            get_time=lambda: time.monotonic() - self._camera_start_time,
            codec="YUYV",
        )
        self._camera.add_color(
            "blue",
            hsv_ranges=[],
            lab_ranges=[],
            sat_min=0,
            min_area=DEFAULT_MIN_AREA,
            min_dimension=5,
        )
        self._camera.add_color(
            "pink",
            hsv_ranges=[],
            lab_ranges=[],
            sat_min=0,
            min_area=DEFAULT_MIN_AREA,
            min_dimension=5,
        )

        self._camera_start_time: float = 0.0
        self._lock = threading.Lock()
        self._latest_color: str | None = None
        self._color_locked: bool = False
        self._detection_paused: bool = False
        self._detection_thread: threading.Thread | None = None
        self._running = False
        self._color_event = threading.Event()

    def start_camera(self) -> None:
        """Start background capture and continuous detection."""
        self._camera_start_time = time.monotonic()
        self._camera.start()
        self._running = True
        self._detection_thread = threading.Thread(
            target=self._detection_loop, daemon=True
        )
        self._detection_thread.start()
        self.info("Camera started - continuous color detection running")

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

        total_analysis_ms = 0.0
        max_analysis_ms = 0.0
        total_wait_ms = 0.0
        max_wait_ms = 0.0
        color_counts: dict[str | None, int] = {}

        while self._running:
            if self._detection_paused:
                time.sleep(0.05)
                continue
            t_wait_start = time.monotonic()
            current_frame_id = self._camera.total_frames
            if current_frame_id < ANALYSIS_FRAMES or current_frame_id == last_frame_id:
                time.sleep(0.005)
                continue
            wait_ms = (time.monotonic() - t_wait_start) * 1000
            total_wait_ms += wait_ms
            max_wait_ms = max(max_wait_ms, wait_ms)
            last_frame_id = current_frame_id

            t0 = time.monotonic()
            result = self._camera.analyze(
                last_n_frames=ANALYSIS_FRAMES,
                presence_threshold=PRESENCE_THRESHOLD,
            )
            analysis_ms = (time.monotonic() - t0) * 1000
            total_analysis_ms += analysis_ms
            max_analysis_ms = max(max_analysis_ms, analysis_ms)
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

            color_counts[color] = color_counts.get(color, 0) + 1

            if color is not None:
                with self._lock:
                    if not self._color_locked:
                        self._latest_color = color
                        self._color_event.set()

            log_elapsed = time.monotonic() - log_window_start
            if log_elapsed >= 5.0:
                detect_fps = detect_count / log_elapsed
                avg_analysis = total_analysis_ms / detect_count if detect_count else 0
                avg_wait = total_wait_ms / detect_count if detect_count else 0
                cam_fps = (
                    self._camera.total_frames
                    / (time.monotonic() - self._camera_start_time)
                    if self._camera_start_time
                    else 0
                )
                buf = self._camera.buffer_count

                try:
                    load1, load5, load15 = os.getloadavg()
                    cpu_str = f"load={load1:.1f}/{load5:.1f}/{load15:.1f}"
                except OSError:
                    cpu_str = "load=N/A"

                colors_str = " ".join(
                    f"{c or 'none'}={n}"
                    for c, n in sorted(color_counts.items(), key=lambda x: -x[1])
                )

                self.info(
                    f"Detection: {detect_fps:.1f}Hz | "
                    f"analysis avg={avg_analysis:.0f}ms max={max_analysis_ms:.0f}ms | "
                    f"wait avg={avg_wait:.0f}ms max={max_wait_ms:.0f}ms | "
                    f"cam={cam_fps:.1f}fps buf={buf} | "
                    f"colors=[{colors_str}] | "
                    f"{cpu_str}"
                )

                detect_count = 0
                total_analysis_ms = 0.0
                max_analysis_ms = 0.0
                total_wait_ms = 0.0
                max_wait_ms = 0.0
                color_counts.clear()
                log_window_start = time.monotonic()

    def pause_detection(self) -> None:
        """Pause the background detection loop to free CPU."""
        self._detection_paused = True

    def resume_detection(self) -> None:
        """Resume the background detection loop."""
        self._detection_paused = False

    def detect_single_frame(self) -> str | None:
        """Grab the latest frame and run single-frame detection."""
        frame = self._camera.grab_frame()
        if frame is None:
            return None

        results = self._camera._analyze_frame(frame)

        blue = results.get("blue")
        pink = results.get("pink")
        blue_present = blue is not None and blue.present
        pink_present = pink is not None and pink.present

        if blue_present and pink_present:
            return "blue" if blue.area >= pink.area else "pink"
        if blue_present:
            return "blue"
        if pink_present:
            return "pink"
        return None

    def lock_color(self) -> str | None:
        """Freeze the current detected color until reset()."""
        with self._lock:
            self._color_locked = True
            color = self._latest_color
        self.info(f"Color locked: {color}")
        return color

    def reset(self) -> None:
        """Clear cached detection and unlock for the next drum cycle."""
        with self._lock:
            self._latest_color = None
            self._color_locked = False
            self._color_event.clear()

    async def wait_for_color(self, timeout: float) -> bool:
        """Await until the background loop detects a color, or timeout."""
        import asyncio

        loop = asyncio.get_event_loop()
        detected = await loop.run_in_executor(None, self._color_event.wait, timeout)
        return detected

    @property
    def peek_color(self) -> str | None:
        """Read the current detected color without consuming it."""
        with self._lock:
            return self._latest_color

    async def detect_color(self) -> str | None:
        """Return the last detected color and clear it."""
        with self._lock:
            color = self._latest_color
            self._latest_color = None

        if color is None:
            self.error("No color detected by camera - could not determine drum color")
            return None

        self.info(f"Detected color: {color}")
        return color

    def apply_calibration(self, sat_threshold: int) -> None:
        """Apply sat_threshold from ColorCalibrationStep."""
        self._camera.set_sat_threshold(sat_threshold)
        self._camera.remove_color("blue")
        self._camera.add_color(
            "blue",
            hsv_ranges=[],
            lab_ranges=[],
            sat_min=sat_threshold,
            min_area=DEFAULT_MIN_AREA,
            min_dimension=5,
        )
        self._camera.remove_color("pink")
        self._camera.add_color(
            "pink",
            hsv_ranges=[],
            lab_ranges=[],
            sat_min=sat_threshold,
            min_area=DEFAULT_MIN_AREA,
            min_dimension=5,
        )
        self.info(f"Color calibration applied: sat_threshold={sat_threshold}")
