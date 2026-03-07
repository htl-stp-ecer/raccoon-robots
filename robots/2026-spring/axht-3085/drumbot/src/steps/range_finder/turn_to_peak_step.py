"""Peak-tracking turn: reuses TurnMotion for search and return phases."""
from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING

from libstp import dsl
from libstp.motion import TurnMotion, TurnConfig
from libstp.step.motion.motion_step import MotionStep

from src.service.range_finder_service import RangeFinderService

if TYPE_CHECKING:
    from libstp.robot.api import GenericRobot


class _Phase(Enum):
    SEARCH = 1       # turning, waiting for T_enter
    TRACK_PEAK = 2   # inside spike zone, tracking max
    RETURN = 3       # rotating back to peak heading


@dsl(hidden=True)
class TurnToPeakStep(MotionStep):
    """Turn until T_enter, track peak heading, then TurnMotion back to it."""

    def __init__(self, direction: float, turn_speed: float, search_deg: float):
        super().__init__()
        self._direction = direction
        self._turn_speed = turn_speed
        self._search_deg = search_deg
        self._phase = _Phase.SEARCH
        self._motion: TurnMotion | None = None
        self._peak_value: float = 0.0
        self._peak_heading: float = 0.0
        self._service: RangeFinderService | None = None

    def _generate_signature(self) -> str:
        d = "right" if self._direction < 0 else "left"
        return f"TurnToPeak(dir={d}, speed={self._turn_speed:.2f}, search={self._search_deg:.0f})"

    def _make_turn(self, robot: "GenericRobot", angle_rad: float) -> TurnMotion:
        cfg = TurnConfig()
        cfg.target_angle_rad = angle_rad
        cfg.speed_scale = self._turn_speed
        motion = TurnMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        motion.start()
        return motion

    def on_start(self, robot: "GenericRobot") -> None:
        self._service = robot.get_service(RangeFinderService)
        rf = self._service.range_finder
        assert rf.is_calibrated, "RangeFinder must be calibrated before turn_to_peak"
        rf.reset_filter()

        # Start a search turn in the given direction
        search_rad = self._direction * math.radians(self._search_deg)
        self._motion = self._make_turn(robot, search_rad)
        self._phase = _Phase.SEARCH
        self.info(f"Peak turn: searching (T_enter={rf.t_enter:.0f}, T_exit={rf.t_exit:.0f})")

    def on_update(self, robot: "GenericRobot", dt: float) -> bool:
        self._motion.update(dt)
        rf = self._service.range_finder
        value = rf.read_filtered()
        heading = robot.odometry.get_heading()

        if self._phase == _Phase.SEARCH:
            if rf.is_above_enter(value):
                self._peak_value = value
                self._peak_heading = heading
                self._phase = _Phase.TRACK_PEAK
                self.info(f"Peak turn: entered spike zone (value={value:.0f})")
            elif self._motion.is_finished():
                self.warn("Peak turn: search turn finished without finding T_enter")
                return True
            return False

        if self._phase == _Phase.TRACK_PEAK:
            if value > self._peak_value:
                self._peak_value = value
                self._peak_heading = heading

            if rf.is_below_exit(value):
                self.info(
                    f"Peak turn: exited spike zone "
                    f"(peak={self._peak_value:.0f} at {math.degrees(self._peak_heading):.1f} deg)"
                )
                # Return to peak heading using odometry error
                error_rad = robot.odometry.get_heading_error(self._peak_heading)
                self._motion = self._make_turn(robot, error_rad)
                self._phase = _Phase.RETURN
            return False

        # RETURN phase
        return self._motion.is_finished()


@dsl(tags=["motion", "sensor"])
def turn_to_peak(
    direction: float = -1.0,
    turn_speed: float = 0.5,
    search_deg: float = 180.0,
) -> TurnToPeakStep:
    """Peak-tracking turn using the calibrated ET range finder.

    Turns until the sensor crosses T_enter, tracks the heading of the
    maximum reading, then uses TurnMotion to rotate back to that peak
    heading when the reading drops below T_exit.

    Prerequisites:
        Range finder must be calibrated via ``calibrate_range_finder()``.

    Args:
        direction: -1.0 for right, +1.0 for left (default: right).
        turn_speed: Fraction of max angular speed, 0.0-1.0 (default 0.5).
        search_deg: Max degrees to search before giving up (default 180).

    Returns:
        A TurnToPeakStep instance.

    Example::

        from src.steps.range_finder import turn_to_peak

        turn_to_peak(direction=-1.0, turn_speed=0.3)
    """
    return TurnToPeakStep(
        direction=direction,
        turn_speed=turn_speed,
        search_deg=search_deg,
    )
