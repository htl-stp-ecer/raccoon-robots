"""Drop-in fake ColorDetectionService for offline testing without a camera.

Returns alternating blue/pink detections so the full collect → sort → eject
pipeline can be exercised without hardware.

Usage in tests (with mock robot):
    fake = FakeColorDetectionService(robot, sequence=["blue", "pink"] * 4)
    robot.get_service.side_effect = lambda cls: fake if cls is ColorDetectionService else ...

Usage on-device (register before missions run):
    from src.service.fake_color_detection_service import install_fake_color_service
    install_fake_color_service(robot)
"""

import asyncio
import threading
import time

from raccoon import GenericRobot, RobotService


# Alternating sequence — matches the real game: 8 drums, 4 of each color.
_DEFAULT_SEQUENCE = ["blue", "pink"] * 4


class FakeColorDetectionService(RobotService):
    """Camera-free color detection that cycles through a fixed sequence."""

    def __init__(self, robot: "GenericRobot", sequence: list[str] | None = None) -> None:
        super().__init__(robot)
        self._sequence = list(sequence or _DEFAULT_SEQUENCE)
        self._index = 0
        self._lock = threading.Lock()
        self._latest_color: str | None = None
        self._color_locked: bool = False
        self._color_event = threading.Event()
        self._color_first_seen: float | None = None
        self._running = False

    # ── Camera lifecycle (no-ops) ─────────────────────────────────

    def start_camera(self) -> None:
        self._running = True
        self.info("FakeColorDetectionService: camera start (no-op)")

    def stop_camera(self) -> None:
        self._running = False
        self.info("FakeColorDetectionService: camera stop (no-op)")

    def pause_detection(self) -> None:
        pass

    def resume_detection(self) -> None:
        pass

    def apply_calibration(self, sat_threshold: int) -> None:
        self.info(f"FakeColorDetectionService: calibration applied (no-op, sat={sat_threshold})")

    # ── Properties ────────────────────────────────────────────────

    @property
    def continuous_color_seconds(self) -> float | None:
        first = self._color_first_seen
        if first is None:
            return None
        return time.monotonic() - first

    @property
    def peek_color(self) -> str | None:
        with self._lock:
            return self._latest_color

    # ── Detection interface ───────────────────────────────────────

    def _next_color(self) -> str:
        """Return the next color in the sequence, cycling if needed."""
        if not self._sequence:
            return "blue"
        color = self._sequence[self._index % len(self._sequence)]
        self._index += 1
        return color

    def reset(self) -> None:
        with self._lock:
            self._latest_color = None
            self._color_locked = False
            self._color_event.clear()
        self._color_first_seen = None

    def lock_color(self) -> str | None:
        with self._lock:
            self._color_locked = True
            color = self._latest_color
        self.info(f"Color locked: {color}")
        return color

    async def wait_for_color(self, timeout: float) -> bool:
        """Simulate a drum arriving after a short delay."""
        await asyncio.sleep(min(0.05, timeout))
        color = self._next_color()
        with self._lock:
            if not self._color_locked:
                self._latest_color = color
                self._color_event.set()
        self._color_first_seen = time.monotonic()
        return True

    async def detect_color(self) -> str | None:
        with self._lock:
            color = self._latest_color
            self._latest_color = None
            self._color_locked = False
            self._color_event.clear()
        self._color_first_seen = None
        if color is None:
            self.error("No color detected (fake service)")
            return None
        self.info(f"Detected color: {color}")
        return color


def install_fake_color_service(
    robot: "GenericRobot",
    sequence: list[str] | None = None,
) -> "FakeColorDetectionService":
    """Register a FakeColorDetectionService under the real class key.

    After this call, ``robot.get_service(ColorDetectionService)`` returns
    the fake instance. Call this before any mission that uses the camera.
    """
    from src.service.color_detection_service import ColorDetectionService

    fake = FakeColorDetectionService(robot, sequence=sequence)
    robot._services[ColorDetectionService] = fake
    return fake
