import asyncio
import math
from libstp import *

from src.hardware.defs import Defs


@dsl_step(tags=["sensor"])
class EtScanAlign(Step):
    """Rotates while sampling the ET sensor, detects an object's edges,
    then centers the heading between start and end of the object.
    Optionally strafes to also center laterally on the object.

    The sensor is expected to read *above* `threshold` when it sees the object
    and *below* when it sees empty space (>30 cm away).

    Args:
        scan_degrees: Total degrees to sweep (positive = amount of rotation).
        direction: "left" or "right" — which way to sweep.
        speed: Rotation speed (0.0–1.0).
        threshold: Analog value above which the object is considered detected.
        sensor: The ET sensor to sample (defaults to Defs.et_sensor).
        strafe_scan: If True, after heading alignment strafe to center laterally.
        strafe_scan_cm: How far to strafe during the lateral scan.
        strafe_direction: "left" or "right" — which way to strafe for the scan.
        strafe_speed: Strafe speed for both the scan and the centering move.
    """

    def __init__(
        self,
        scan_degrees: float = 90,
        direction: str = "left",
        speed: float = 0.4,
        threshold: float = 1500,
        sensor=None,
        strafe_scan: bool = False,
        strafe_scan_cm: float = 30,
        strafe_direction: str = "left",
        strafe_speed: float = 0.3,
    ):
        super().__init__()
        self.scan_degrees = scan_degrees
        self.direction = direction
        self.speed = speed
        self.threshold = threshold
        self.sensor = sensor or Defs.et_sensor
        self.strafe_scan = strafe_scan
        self.strafe_scan_cm = strafe_scan_cm
        self.strafe_direction = strafe_direction
        self.strafe_speed = strafe_speed
        self._samples: list[tuple[float, float]] = []  # (heading_deg, value)
        self._strafe_samples: list[tuple[float, float]] = []  # (lateral_cm_rel, value)

    async def _execute_step(self, robot) -> None:
        # Phase 1: Scan — turn while sampling the ET sensor
        self._samples = []
        sampling = True

        async def sample_loop():
            while sampling:
                heading_deg = math.degrees(robot.defs.imu.get_heading())
                value = self.sensor.read()
                self._samples.append((heading_deg, value))
                await asyncio.sleep(0.01)  # ~100 Hz

        # Build the turn step
        if self.direction == "left":
            scan_step = turn_left(self.scan_degrees, self.speed)
        else:
            scan_step = turn_right(self.scan_degrees, self.speed)

        # Run turn and sampling concurrently
        sample_task = asyncio.create_task(sample_loop())
        try:
            await scan_step._execute_step(robot)
        finally:
            sampling = False
            await sample_task

        # Phase 2: Analyze — find object center
        target = self._find_center()
        if target is None:
            return  # nothing detected

        # Phase 3: Center — turn to the midpoint heading
        current = math.degrees(robot.defs.imu.get_heading())
        error = self._angle_diff(target, current)

        if abs(error) < 1.0:
            return  # already centered

        if error > 0:
            center_step = turn_left(abs(error), self.speed)
        else:
            center_step = turn_right(abs(error), self.speed)

        await center_step._execute_step(robot)

        if not self.strafe_scan:
            return

        # Phase 4: Strafe scan — strafe while sampling to find lateral center
        self._strafe_samples = []
        start_lateral_m = robot.odometry.get_distance_from_origin().lateral
        strafe_sampling = True

        async def strafe_sample_loop():
            while strafe_sampling:
                lateral_cm = (robot.odometry.get_distance_from_origin().lateral - start_lateral_m) * 100
                value = self.sensor.read()
                self._strafe_samples.append((lateral_cm, value))
                await asyncio.sleep(0.01)

        if self.strafe_direction == "left":
            strafe_step = strafe_left(self.strafe_scan_cm, self.strafe_speed)
        else:
            strafe_step = strafe_right(self.strafe_scan_cm, self.strafe_speed)

        strafe_task = asyncio.create_task(strafe_sample_loop())
        try:
            await strafe_step._execute_step(robot)
        finally:
            strafe_sampling = False
            await strafe_task

        # Phase 5: Strafe to lateral center
        lateral_target_cm = self._find_lateral_center()
        if lateral_target_cm is None:
            return

        current_lateral_cm = (robot.odometry.get_distance_from_origin().lateral - start_lateral_m) * 100
        error_cm = lateral_target_cm - current_lateral_cm

        if abs(error_cm) < 0.5:
            return

        if error_cm > 0:
            center_strafe = strafe_right(abs(error_cm), self.strafe_speed)
        else:
            center_strafe = strafe_left(abs(error_cm), self.strafe_speed)

        await center_strafe._execute_step(robot)

    # --- analysis ---

    def _find_lateral_center(self) -> float | None:
        """Find the center lateral position (cm, relative to strafe scan start)."""
        if not self._strafe_samples:
            return None
        above = [(lat, v) for lat, v in self._strafe_samples if v >= self.threshold]
        if not above:
            return None
        return (above[0][0] + above[-1][0]) / 2

    def _find_center(self) -> float | None:
        """Find the center heading between the first and last threshold crossing."""
        if not self._samples:
            return None

        above = [(h, v) for h, v in self._samples if v >= self.threshold]
        if not above:
            return None

        obj_start_heading = above[0][0]
        obj_end_heading = above[-1][0]

        return self._midpoint_angle(obj_start_heading, obj_end_heading)

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

    @property
    def strafe_samples(self) -> list[tuple[float, float]]:
        return list(self._strafe_samples)

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
        return frozenset({})
