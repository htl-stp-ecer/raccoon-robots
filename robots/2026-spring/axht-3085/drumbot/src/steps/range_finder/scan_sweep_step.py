"""Sweep motion step: reuses TurnMotion to turn right while sampling."""
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


@dsl(hidden=True)
class ScanSweepStep(MotionStep):
    """Reuses TurnMotion to sweep right while sampling the ET sensor."""

    def __init__(self, sweep_deg: float, turn_speed: float):
        super().__init__()
        self._sweep_deg = sweep_deg
        self._turn_speed = turn_speed
        self._phase = _Phase.SWEEP
        self._motion: TurnMotion | None = None
        self._start_heading: float = 0.0
        self._service: RangeFinderService | None = None
        self.samples: list[tuple[float, float]] = []

    def _generate_signature(self) -> str:
        return f"ScanSweep(sweep={self._sweep_deg:.0f}, speed={self._turn_speed:.2f})"

    def _make_turn(self, robot: GenericRobot, angle_rad: float) -> TurnMotion:
        cfg = TurnConfig()
        cfg.target_angle_rad = angle_rad
        cfg.speed_scale = self._turn_speed
        motion = TurnMotion(robot.drive, robot.odometry, robot.motion_pid_config, cfg)
        motion.start()
        return motion

    def on_start(self, robot: GenericRobot) -> None:
        self._service = robot.get_service(RangeFinderService)
        self._service.range_finder.reset_filter()
        self._start_heading = robot.odometry.get_heading()

        sweep_rad = math.radians(self._sweep_deg)
        self._phase = _Phase.SWEEP
        self._motion = self._make_turn(robot, -sweep_rad)  # negative = CW = right
        self.info(f"Sweep: scanning right {self._sweep_deg:.0f} deg")

    def on_update(self, robot: GenericRobot, dt: float) -> bool:
        self._motion.update(dt)
        rf = self._service.range_finder

        # SWEEP phase: sample while turning right
        value = rf.read_filtered()
        heading = robot.odometry.get_heading()
        relative_deg = math.degrees(heading - self._start_heading)
        self.samples.append((relative_deg, value))

        if self._motion.is_finished():
            self.info(f"Sweep complete: {len(self.samples)} samples")
            return True
        return False


@dsl(tags=["motion", "sensor"])
def scan_sweep(
    sweep_deg: float = 45.0,
    turn_speed: float = 0.2,
) -> ScanSweepStep:
    """Sweep right while sampling the ET range finder."""
    return ScanSweepStep(
        sweep_deg=sweep_deg,
        turn_speed=turn_speed,
    )
