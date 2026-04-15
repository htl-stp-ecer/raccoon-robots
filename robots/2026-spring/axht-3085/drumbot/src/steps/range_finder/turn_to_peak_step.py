"""Peak-tracking turn: full sweep then turn to absolute peak heading."""
from __future__ import annotations

import csv
import math
import os
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from raccoon import dsl
from raccoon.motion import TurnConfig, TurnMotion
from raccoon.step.motion.motion_step import MotionStep

from src.service.range_finder_service import RangeFinderService

if TYPE_CHECKING:
    from raccoon.robot.api import GenericRobot

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs", "turn_to_peak")


class _Phase(Enum):
    SWEEP = 1   # full sweep, tracking peak heading
    RETURN = 2  # turning to absolute peak heading


@dsl(hidden=True)
class TurnToPeakStep(MotionStep):
    """Full sweep tracking peak sensor value, then turn to that absolute heading."""

    STUCK_WINDOW = 0.3          # seconds of no heading change to consider stuck
    STUCK_THRESHOLD_DEG = 2.0   # minimum heading change within window

    def __init__(self, direction: float, turn_speed: float, sweep_deg: float):
        super().__init__()
        self._direction = direction
        self._turn_speed = turn_speed
        self._sweep_deg = sweep_deg
        self._phase = _Phase.SWEEP
        self._motion: TurnMotion | None = None
        self._peak_value: float = 0.0
        self._peak_heading: float = 0.0
        self._service: RangeFinderService | None = None
        self._stuck_ref_heading: float = 0.0
        self._stuck_ref_time: float = 0.0
        self._elapsed: float = 0.0
        self._log_rows: list[tuple[float, float, float, float, float, str]] = []

    def _generate_signature(self) -> str:
        d = "right" if self._direction < 0 else "left"
        return f"TurnToPeak(dir={d}, speed={self._turn_speed:.2f}, sweep={self._sweep_deg:.0f})"

    def _make_turn(self, robot: GenericRobot, angle_rad: float) -> TurnMotion:
        cfg = TurnConfig()
        cfg.target_angle_rad = angle_rad
        cfg.speed_scale = self._turn_speed
        motion = TurnMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        motion.start()
        return motion

    def on_start(self, robot: GenericRobot) -> None:
        self._service = robot.get_service(RangeFinderService)
        rf = self._service.range_finder
        rf.reset_filter()

        # Start full sweep in the given direction
        sweep_rad = self._direction * math.radians(self._sweep_deg)
        self._motion = self._make_turn(robot, sweep_rad)
        self._phase = _Phase.SWEEP

        # Initialize peak and stuck detection
        self._peak_value = rf.read_filtered()
        self._peak_heading = robot.odometry.get_heading()
        self._stuck_ref_heading = self._peak_heading
        self._stuck_ref_time = 0.0
        self._elapsed = 0.0
        self.info(f"Peak turn: sweeping {self._sweep_deg:.0f} deg")

    def _is_stuck(self, heading: float, dt: float) -> bool:
        self._elapsed += dt
        heading_delta = abs(math.degrees(heading - self._stuck_ref_heading))
        if heading_delta > self.STUCK_THRESHOLD_DEG:
            self._stuck_ref_heading = heading
            self._stuck_ref_time = self._elapsed
        return self._elapsed - self._stuck_ref_time >= self.STUCK_WINDOW

    def _transition_to_return(self, robot: GenericRobot, reason: str) -> None:
        self.info(
            f"Peak turn: {reason}, peak={self._peak_value:.0f} "
            f"at {math.degrees(self._peak_heading):.1f} deg"
        )
        error_rad = robot.odometry.get_heading_error(self._peak_heading)
        self._motion = self._make_turn(robot, error_rad)
        self._phase = _Phase.RETURN

    def _save_log(self) -> None:
        if not self._log_rows:
            return
        os.makedirs(LOG_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(LOG_DIR, f"{stamp}.csv")
        png_path = os.path.join(LOG_DIR, f"{stamp}.png")

        with open(csv_path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["elapsed_s", "heading_deg", "sensor_value", "peak_value", "peak_heading_deg", "phase"])
            w.writerows(self._log_rows)

        self.info(f"Peak turn log saved: {csv_path}")

    def on_update(self, robot: GenericRobot, dt: float) -> bool:
        self._motion.update(dt)
        rf = self._service.range_finder
        value = rf.read_filtered()
        heading = robot.odometry.get_heading()

        self._log_rows.append((
            self._elapsed,
            math.degrees(heading),
            value,
            self._peak_value,
            math.degrees(self._peak_heading),
            self._phase.name,
        ))

        if self._phase == _Phase.SWEEP:
            if value > self._peak_value:
                self._peak_value = value
                self._peak_heading = heading

            if self._is_stuck(heading, dt):
                self._transition_to_return(robot, "stuck — aborting sweep")
            elif self._motion.is_finished():
                self._transition_to_return(robot, "sweep done")
            else:
                return False
            return False

        # RETURN phase
        done = self._motion.is_finished()
        if done:
            self._save_log()
        return done


@dsl(tags=["motion", "sensor"])
def turn_to_peak(
    direction: float = -1.0,
    turn_speed: float = 0.5,
    sweep_deg: float = 35,
) -> TurnToPeakStep:
    """Peak-tracking turn using the ET range finder.

    Does a full sweep, tracking the heading of the maximum sensor reading,
    then turns to that absolute heading.

    Args:
        direction: -1.0 for right, +1.0 for left (default: right).
        turn_speed: Fraction of max angular speed, 0.0-1.0 (default 0.5).
        sweep_deg: Degrees to sweep (default 30).

    Returns:
        A TurnToPeakStep instance.
    """
    return TurnToPeakStep(
        direction=direction,
        turn_speed=turn_speed,
        sweep_deg=sweep_deg,
    )
