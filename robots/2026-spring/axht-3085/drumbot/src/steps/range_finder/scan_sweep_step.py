"""Sweep motion step: reuses TurnMotion to turn left then right while sampling."""
from __future__ import annotations

import math
from enum import Enum
from typing import TYPE_CHECKING, List, Tuple

from libstp import dsl
from libstp.motion import TurnMotion, TurnConfig
from libstp.step.motion.motion_step import MotionStep

from src.service.range_finder_service import RangeFinderService

if TYPE_CHECKING:
    from libstp.robot.api import GenericRobot


class _Phase(Enum):
    TURN_TO_START = 1
    SWEEP = 2


@dsl(hidden=True)
class ScanSweepStep(MotionStep):
    """Reuses TurnMotion to turn left, then sweep right while sampling the ET sensor."""

    def __init__(self, sweep_deg: float, turn_speed: float):
        super().__init__()
        self._sweep_deg = sweep_deg
        self._turn_speed = turn_speed
        self._phase = _Phase.TURN_TO_START
        self._motion: TurnMotion | None = None
        self._start_heading: float = 0.0
        self._service: RangeFinderService | None = None
        self.samples: List[Tuple[float, float]] = []

    def _generate_signature(self) -> str:
        return f"ScanSweep(sweep={self._sweep_deg:.0f}, speed={self._turn_speed:.2f})"

    def _make_turn(self, robot: "GenericRobot", angle_rad: float) -> TurnMotion:
        cfg = TurnConfig()
        cfg.target_angle_rad = angle_rad
        cfg.speed_scale = self._turn_speed
        motion = TurnMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        motion.start()
        return motion

    def on_start(self, robot: "GenericRobot") -> None:
        self._service = robot.get_service(RangeFinderService)
        self._service.range_finder.reset_filter()
        self._start_heading = robot.odometry.get_heading()

        half_rad = math.radians(self._sweep_deg) / 2.0
        self._phase = _Phase.TURN_TO_START
        self._motion = self._make_turn(robot, half_rad)  # positive = CCW = left
        self.info(f"Sweep: turning left {self._sweep_deg / 2:.0f} deg")

    def on_update(self, robot: "GenericRobot", dt: float) -> bool:
        self._motion.update(dt)
        rf = self._service.range_finder

        if self._phase == _Phase.TURN_TO_START:
            if self._motion.is_finished():
                self._phase = _Phase.SWEEP
                rf.reset_filter()
                sweep_rad = math.radians(self._sweep_deg)
                self._motion = self._make_turn(robot, -sweep_rad)  # negative = CW = right
                self.info(f"Sweep: scanning right {self._sweep_deg:.0f} deg")
            return False

        # SWEEP phase: sample while turning
        value = rf.read_filtered()
        heading = robot.odometry.get_heading()
        relative_deg = math.degrees(heading - self._start_heading)
        self.samples.append((relative_deg, value))

        if self._motion.is_finished():
            self.info(f"Sweep complete: {len(self.samples)} samples")
            return True
        return False
