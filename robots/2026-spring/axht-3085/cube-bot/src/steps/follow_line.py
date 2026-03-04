"""
Line following using IR sensors.

This module provides steps for following lines using one or two IR sensors
with PID-based steering control, built on top of LinearMotion for proper
profiled distance control and odometry integration.
"""
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from libstp.foundation import PidConfig, PidController
from libstp.motion import LinearMotion, LinearMotionConfig, LinearAxis
from libstp.sensor_ir import IRSensor

from libstp import SimulationStep, SimulationStepDelta, dsl
from libstp import MotionStep

if TYPE_CHECKING:
    from libstp.robot.api import GenericRobot


class LineSide(Enum):
    """Which edge of the line to track with a single sensor."""
    LEFT = "left"
    RIGHT = "right"


@dataclass
class BetterSingleLineFollowConfig:
    """Configuration for single-sensor line following.

    The sensor tracks the edge of a line using PID control.
    ``side`` selects which edge: LEFT means the sensor approaches
    from the left (steers right when it sees black), RIGHT is the
    opposite.
    """
    sensor: IRSensor
    speed_scale: float  # 0-1 fraction of max velocity
    distance_cm: float  # distance to follow
    side: LineSide = LineSide.LEFT
    kp: float = 1.0
    ki: float = 0.0
    kd: float = 0.3
    threshold: float = 0.5
    second_sensor: IRSensor | None = None


@dsl(hidden=True)
class BetterSingleSensorLineFollow(MotionStep):
    """
    Follow a line using a single IR sensor with PID edge-tracking.

    Uses LinearMotion for profiled distance control and odometry,
    with sensor-based PID steering overriding the heading controller.
    """

    def __init__(self, config: BetterSingleLineFollowConfig):
        super().__init__()
        self.config = config
        self._motion: LinearMotion | None = None
        self._pid: PidController | None = None

    def _generate_signature(self) -> str:
        return (
            f"SingleSensorLineFollow(distance={self.config.distance_cm:.1f}cm, "
            f"side={self.config.side.value}, speed={self.config.speed_scale:.2f})"
        )

    def to_simulation_step(self) -> SimulationStep:
        base = super().to_simulation_step()
        base.delta = SimulationStepDelta(
            forward=self.config.distance_cm / 100.0,
            strafe=0.0,
            angular=0.0,
        )
        return base

    def on_start(self, robot: "GenericRobot") -> None:
        cfg = self.config

        motion_config = LinearMotionConfig()
        motion_config.axis = LinearAxis.Forward
        motion_config.distance_m = cfg.distance_cm / 100.0
        motion_config.speed_scale = cfg.speed_scale

        self._motion = LinearMotion(
            robot.drive, robot.odometry, robot.motion_pid_config, motion_config,
        )
        self._motion.start()

        self._pid = PidController(PidConfig(kp=cfg.kp, ki=cfg.ki, kd=cfg.kd))

        self.debug(
            f"on_start: distance={cfg.distance_cm:.1f}cm, side={cfg.side.value}, "
            f"speed_scale={cfg.speed_scale:.2f}, PID({cfg.kp}, {cfg.ki}, {cfg.kd})"
        )

    def on_update(self, robot: "GenericRobot", dt: float) -> bool:
        cfg = self.config

        # Edge-tracking error: 0.5 = edge of line
        reading = cfg.sensor.probabilityOfBlack()
        error = reading - cfg.threshold
        if cfg.side == LineSide.RIGHT:
            error = -error

        # PID steering -> omega override on LinearMotion
        wz = self._pid.update(error, dt)
        self._motion.set_omega_override(wz)

        self.debug(
            f"black={reading:.2f} err={error:.2f} wz={wz:.3f} dt={dt:.4f}"
        )

        self._motion.update(dt)
        if cfg.second_sensor is None:
            return self._motion.is_finished()

        stop_reading = cfg.second_sensor.probabilityOfBlack()
        if stop_reading >= cfg.threshold:
            return True

        return False


@dsl(tags=["motion", "line-follow"])
def better_follow_line_single(
    sensor: IRSensor,
    distance_cm: float,
    speed: float = 0.5,
    side: LineSide = LineSide.LEFT,
    kp: float = 1.0,
    ki: float = 0.0,
    kd: float = 0.3,
    threshold: float = 0.5,
) -> BetterSingleSensorLineFollow:
    """
    Follow a line using a single sensor for a specified distance.

    The sensor tracks the edge of the line (where probabilityOfBlack ~ 0.5).
    ``side`` selects which edge to follow.

    Args:
        sensor: The IR sensor instance
        distance_cm: Distance to follow in centimeters
        speed: Fraction of max speed, 0-1 (default 0.5)
        side: Which edge to track (LEFT or RIGHT)
        kp, ki, kd: PID gains for steering

    Returns:
        SingleSensorLineFollow step
    """
    config = BetterSingleLineFollowConfig(
        sensor=sensor,
        speed_scale=speed,
        side=side,
        distance_cm=distance_cm,
        kp=kp, ki=ki, kd=kd,
        threshold=threshold,
    )
    return BetterSingleSensorLineFollow(config)

@dsl(tags=["motion", "line-follow"])
def better_follow_line_single_until_line(
        sensor: IRSensor,
        second_sensor: IRSensor,
        speed: float = 0.5,
        side: LineSide = LineSide.LEFT,
        kp: float = 1.0,
        ki: float = 0.0,
        kd: float = 0.3,
        threshold: float = 0.5,
) -> BetterSingleSensorLineFollow:
    """
    Follow a line using a single sensor for a specified distance.

    The sensor tracks the edge of the line (where probabilityOfBlack ~ 0.5).
    ``side`` selects which edge to follow.

    Args:
        sensor: The IR sensor instance
        second_sensor: The IR sensor instance
        speed: Fraction of max speed, 0-1 (default 0.5)
        side: Which edge to track (LEFT or RIGHT)
        kp, ki, kd: PID gains for steering

    Returns:
        SingleSensorLineFollow step
    """
    config = BetterSingleLineFollowConfig(
        sensor=sensor,
        distance_cm=0,
        speed_scale=speed,
        side=side,
        kp=kp, ki=ki, kd=kd,
        threshold=threshold,
        second_sensor=second_sensor,
    )
    return BetterSingleSensorLineFollow(config)
