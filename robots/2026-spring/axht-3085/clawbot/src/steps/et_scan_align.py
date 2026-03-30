import math
from libstp import *

from src.hardware.defs import Defs


@dsl_step(tags=["motion", "sensor"])
class EtScanAlign(MotionStep):
    """Rotates while sampling the ET sensor, detects an object's edges,
    then centers the heading between start and end of the object.

    The sensor is expected to read *above* `threshold` when it sees the object
    and *below* when it sees empty space (>30 cm away).

    Args:
        scan_degrees: Total degrees to sweep (positive = amount of rotation).
        direction: "left" or "right" — which way to sweep.
        speed: Rotation speed (0.0–1.0).
        threshold: Analog value above which the object is considered detected.
        sensor: The ET sensor to sample (defaults to Defs.et_sensor).
    """

    def __init__(
        self,
        scan_degrees: float = 90,
        direction: str = "left",
        speed: float = 0.4,
        threshold: float = 1500,
        sensor=None,
    ):
        super().__init__()
        self.scan_degrees = scan_degrees
        self.direction = direction
        self.speed = speed
        self.threshold = threshold
        self.sensor = sensor or Defs.et_sensor
        # filled during scan
        self._samples: list[tuple[float, float]] = []  # (heading_deg, value)
        self._start_heading: float = 0.0
        self._scan_done = False
        self._centering = False
        self._target_heading: float | None = None

    def on_start(self, robot):
        self.drive = robot.drive
        self._start_heading = math.degrees(robot.defs.imu.get_heading())
        self._samples = []
        self._scan_done = False
        self._centering = False
        self._target_heading = None

    def on_update(self, robot, dt) -> bool:
        current_heading = math.degrees(robot.defs.imu.get_heading())

        if not self._scan_done:
            return self._do_scan(robot, current_heading)
        else:
            return self._do_center(robot, current_heading)

    def _do_scan(self, robot, current_heading: float) -> bool:
        # sample the sensor
        value = self.sensor.read()
        self._samples.append((current_heading, value))

        # compute how far we've rotated
        delta = self._angle_diff(current_heading, self._start_heading)
        if abs(delta) >= self.scan_degrees:
            # scan complete — stop, analyse, prepare centering
            robot.drive.hard_stop()
            self._scan_done = True
            self._target_heading = self._find_center()
            if self._target_heading is None:
                # nothing detected — just stop where we are
                return True
            self._centering = True
            return False

        # keep turning
        wz = self.speed if self.direction == "left" else -self.speed
        self.drive.set_desired_velocity(0, 0, wz)
        return False

    def _do_center(self, robot, current_heading: float) -> bool:
        error = self._angle_diff(self._target_heading, current_heading)
        if abs(error) < 1.0:
            robot.drive.hard_stop()
            return True

        # proportional turn toward the target
        kp = 0.02
        wz = max(-self.speed, min(self.speed, kp * error))
        self.drive.set_desired_velocity(0, 0, wz)
        return False

    def on_stop(self, robot):
        robot.drive.hard_stop()

    # --- analysis ---

    def _find_center(self) -> float | None:
        """Find the center heading between the first and last threshold crossing."""
        if not self._samples:
            return None

        above = [(h, v) for h, v in self._samples if v >= self.threshold]
        if not above:
            return None

        # object start = first sample above threshold
        # object end   = last sample above threshold
        obj_start_heading = above[0][0]
        obj_end_heading = above[-1][0]

        # center heading = midpoint of the arc between start and end
        center = self._midpoint_angle(obj_start_heading, obj_end_heading)
        return center

    @property
    def object_start_heading(self) -> float | None:
        above = [(h, v) for h, v in self._samples if v >= self.threshold]
        return above[0][0] if above else None

    @property
    def object_end_heading(self) -> float | None:
        above = [(h, v) for h, v in self._samples if v >= self.threshold]
        return above[-1][0] if above else None

    @property
    def object_arc_degrees(self) -> float | None:
        start = self.object_start_heading
        end = self.object_end_heading
        if start is None or end is None:
            return None
        return abs(self._angle_diff(end, start))

    @property
    def samples(self) -> list[tuple[float, float]]:
        return list(self._samples)

    # --- helpers ---

    @staticmethod
    def _angle_diff(target: float, current: float) -> float:
        """Signed shortest-path difference (target - current), wrapped to [-180, 180]."""
        diff = target - current
        while diff > 180:
            diff -= 360
        while diff < -180:
            diff += 360
        return diff

    @staticmethod
    def _midpoint_angle(a: float, b: float) -> float:
        """Midpoint of two angles on the circle."""
        diff = EtScanAlign._angle_diff(b, a)
        mid = a + diff / 2
        while mid > 180:
            mid -= 360
        while mid < -180:
            mid += 360
        return mid

    def required_resources(self) -> frozenset[str]:
        return frozenset({"drive"})
