"""Peak turn: sweep an arc sampling the ET sensor, return to peak heading.

Early-stop: once the reading has risen by at least ``min_rise`` from the
start value and then drops by more than ``drop_factor`` of that rise, the
sweep is cut short immediately and the robot turns back to the peak heading.
"""
from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

from libstp import dsl
from libstp.motion import TurnConfig, TurnMotion
from libstp.step.motion.motion_step import MotionStep

from src.service.range_finder_service import RangeFinderService

if TYPE_CHECKING:
    from libstp.robot.api import GenericRobot


class _Phase(Enum):
    SWEEP = 1
    RETURN = 2


@dsl(hidden=True)
class TurnToPeakStep(MotionStep):
    """Sweep sampling the ET sensor, then turn back to the peak heading.

    Stops early if the reading rises significantly and then drops by more
    than ``drop_factor`` of the observed rise.
    """

    def __init__(
        self,
        direction: float,
        turn_speed: float,
        return_speed: float,
        search_deg: float,
        min_rise: float,
        drop_factor: float,
        dead_zone_deg: float,
    ):
        super().__init__()
        self._direction = direction
        self._turn_speed = turn_speed
        self._return_speed = return_speed
        self._search_deg = search_deg
        self._min_rise = min_rise
        self._drop_factor = drop_factor
        self._dead_zone_deg = dead_zone_deg
        self._phase = _Phase.SWEEP
        self._motion: TurnMotion | None = None
        self._start_heading: float = 0.0
        self._start_value: float = 0.0
        self._peak_filtered: float = 0.0   # filtered peak — used for drop detection
        self._centroid_heading: float = 0.0
        self._centroid_weight: float = 0.0
        self._service: RangeFinderService | None = None

    def _generate_signature(self) -> str:
        d = "right" if self._direction < 0 else "left"
        return (
            f"TurnToPeak(dir={d}, speed={self._turn_speed:.2f}, "
            f"search={self._search_deg:.0f}, min_rise={self._min_rise:.0f})"
        )

    def _make_turn(self, robot: GenericRobot, angle_rad: float) -> TurnMotion:
        cfg = TurnConfig()
        cfg.target_angle_rad = angle_rad
        cfg.speed_scale = self._turn_speed
        motion = TurnMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        motion.start()
        return motion

    def _return_to_peak(self, robot: GenericRobot, reason: str) -> None:
        if self._centroid_weight > 0:
            target_heading = self._centroid_heading / self._centroid_weight
        else:
            target_heading = self._start_heading
        self.info(
            f"Peak turn: {reason} — centroid={math.degrees(target_heading):.1f} deg "
            f"(weight={self._centroid_weight:.0f})"
        )
        error_rad = robot.odometry.get_heading_error(target_heading)
        cfg = TurnConfig()
        cfg.target_angle_rad = error_rad
        cfg.speed_scale = self._return_speed
        self._motion = TurnMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        self._motion.start()
        self._phase = _Phase.RETURN

    def on_start(self, robot: GenericRobot) -> None:
        self._service = robot.get_service(RangeFinderService)
        rf = self._service.range_finder
        rf.reset_filter()

        self._start_heading = robot.odometry.get_heading()
        raw = rf.read_raw()
        rf.read_filtered()  # seed EMA with first raw read
        self._start_value = raw
        self._peak_filtered = raw
        self._centroid_heading = self._start_heading
        self._centroid_weight = 0.0

        sweep_rad = self._direction * math.radians(self._search_deg)
        self._motion = self._make_turn(robot, sweep_rad)
        self._phase = _Phase.SWEEP
        self.info(
            f"Peak turn: sweeping {self._search_deg:.0f} deg, "
            f"dead_zone={self._dead_zone_deg:.0f} deg, start={self._start_value:.0f}"
        )

    def on_update(self, robot: GenericRobot, dt: float) -> bool:
        self._motion.update(dt)
        rf = self._service.range_finder
        raw = rf.read_raw()
        filtered = rf.read_filtered()
        heading = robot.odometry.get_heading()

        if self._phase == _Phase.SWEEP:
            swept_deg = abs(math.degrees(heading - self._start_heading))

            # Accumulate weighted centroid using raw signal above baseline
            weight = max(0.0, raw - self._start_value)
            self._centroid_weight += weight
            self._centroid_heading += weight * heading

            # Filtered peak used for drop detection (smoother signal)
            if filtered > self._peak_filtered:
                self._peak_filtered = filtered

            if swept_deg >= self._dead_zone_deg:
                rise = self._peak_filtered - self._start_value
                drop = self._peak_filtered - filtered
                if rise >= self._min_rise and drop >= self._drop_factor * rise:
                    self._return_to_peak(robot, "early stop")
                    return False

            if self._motion.is_finished():
                self._return_to_peak(robot, "sweep complete")
                return False

            return False

        # RETURN phase
        return self._motion.is_finished()


@dsl(tags=["motion", "sensor"])
def turn_to_peak(
    direction: float = -1.0,
    turn_speed: float = 0.3,
    return_speed: float = 0.15,
    search_deg: float = 45.0,
    min_rise: float = 100.0,
    drop_factor: float = 0.4,
    dead_zone_deg: float = 10.0,
) -> TurnToPeakStep:
    """Sweep the ET sensor and turn back to the peak heading.

    Stops early once the reading has risen by at least ``min_rise`` and
    then dropped by more than ``drop_factor`` of that rise.

    Args:
        direction: -1.0 for right, +1.0 for left (default: right).
        turn_speed: Fraction of max angular speed, 0.0-1.0 (default 0.5).
        search_deg: Maximum arc to sweep in degrees (default 45).
        min_rise: Minimum rise from start value to treat as a real peak
            (default 50). Filters out noise before the pipe zone.
        return_speed: Speed for the return turn (default 0.15). Slower than
            sweep so TurnMotion can stop precisely on the peak heading.
        drop_factor: Fraction of the rise that must drop to trigger early
            stop (default 0.4). Lower = stop sooner after peak.
        dead_zone_deg: Degrees to sweep before early stop is eligible
            (default 10). Prevents startup noise from firing the trigger.
    """
    return TurnToPeakStep(
        direction=direction,
        turn_speed=turn_speed,
        return_speed=return_speed,
        search_deg=search_deg,
        min_rise=min_rise,
        drop_factor=drop_factor,
        dead_zone_deg=dead_zone_deg,
    )
