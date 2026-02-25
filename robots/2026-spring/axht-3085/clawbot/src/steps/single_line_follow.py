"""
Line following using IR sensors.

This module provides steps for following lines using one or two IR sensors
with PID-based steering control.
"""
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from libstp import MotionStep, dsl, SimulationStep, SimulationStepDelta
from libstp.foundation import ChassisVelocity, PidConfig, PidController
from libstp.sensor_ir import IRSensor


if TYPE_CHECKING:
    from libstp.robot.api import GenericRobot


class LineSide(Enum):
    """Which edge of the line to track with a single sensor."""
    LEFT = "left"
    RIGHT = "right"


@dataclass
class SingleLineFollowConfig:
    """Configuration for single-sensor line following.

    The sensor tracks the edge of a line using PID control.
    ``side`` selects which edge: LEFT means the sensor approaches
    from the left (steers right when it sees black), RIGHT is the
    opposite.
    """
    sensor: IRSensor
    forward_speed: float  # m/s
    distance_cm: float  # distance to follow
    side: LineSide = LineSide.LEFT
    kp: float = 3.0
    ki: float = 0.0
    kd: float = 0.3
    forward_reduction: float = 0.5  # slow down proportional to |steering|

@dsl(hidden=True)
class SingleSensorLineFollow(MotionStep):
    """
    Follow a line using a single IR sensor with PID edge-tracking.

    The sensor targets the edge of the line (probabilityOfBlack ≈ 0.5).
    PID drives angular velocity to keep the sensor on that edge.
    ``side`` determines which edge is tracked (flips the error sign).

    Terminates after traveling ``distance_cm``.
    """

    def __init__(self, config: SingleLineFollowConfig):
        super().__init__()
        self.config = config
        self._pid: PidController | None = None
        self._target_distance_m: float = 0.0

    def _generate_signature(self) -> str:
        return (
            f"SingleSensorLineFollow(distance={self.config.distance_cm:.1f}cm, "
            f"side={self.config.side.value}, speed={self.config.forward_speed:.2f})"
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
        self._pid = PidController(PidConfig(kp=cfg.kp, ki=cfg.ki, kd=cfg.kd))
        self._target_distance_m = cfg.distance_cm / 100.0
        robot.odometry.reset()

    def on_update(self, robot: "GenericRobot", dt: float) -> bool:
        cfg = self.config

        # --- stop condition: distance traveled ---
        current_pose = robot.odometry.get_pose()
        traveled = abs(current_pose.position[0])
        if traveled >= self._target_distance_m:
            return True

        self.debug(
            f"current_pos={current_pose.position[0]} pose={current_pose}"
            f" traveled={traveled:.2f} target={self._target_distance_m:.2f}"
        )

        # --- edge-tracking error ---
        # 0.5 = edge of line; positive error = too far onto the black
        error = cfg.sensor.probabilityOfBlack() - 0.5
        if cfg.side == LineSide.RIGHT:
            error = -error

        # --- PID steering ---
        wz = self._pid.update(error, dt)

        # reduce forward speed when steering hard
        speed_factor = 1.0 - min(abs(wz) * cfg.forward_reduction, 0.8)
        vx = cfg.forward_speed * speed_factor

        self.debug(
            f"LineFollow1: black={cfg.sensor.probabilityOfBlack():.2f} "
            f"err={error:.2f} wz={wz:.2f} vx={vx:.2f}"
        )

        robot.drive.set_velocity(ChassisVelocity(vx, 0.0, wz))
        robot.drive.update(dt)
        return False


@dsl(tags=["motion", "line-follow"])
def follow_line_single(
    sensor: IRSensor,
    distance_cm: float,
    forward_speed: float = 0.5,
    side: LineSide = LineSide.LEFT,
    kp: float = 1.0,
    ki: float = 0.0,
    kd: float = 0.3,
    forward_reduction: float = 0.5,
) -> SingleSensorLineFollow:
    """
    Follow a line using a single sensor for a specified distance.

    The sensor tracks the edge of the line (where probabilityOfBlack ≈ 0.5).
    ``side`` selects which edge to follow.

    Args:
        sensor: The IR sensor instance
        distance_cm: Distance to follow in centimeters
        forward_speed: Forward speed in m/s
        side: Which edge to track (LEFT or RIGHT)
        kp, ki, kd: PID gains for steering
        forward_reduction: Slow down by this fraction of |steering| on curves

    Returns:
        SingleSensorLineFollow step
    """
    config = SingleLineFollowConfig(
        sensor=sensor,
        forward_speed=forward_speed,
        side=side,
        distance_cm=distance_cm,
        kp=kp, ki=ki, kd=kd,
        forward_reduction=forward_reduction,
    )
    return SingleSensorLineFollow(config)
