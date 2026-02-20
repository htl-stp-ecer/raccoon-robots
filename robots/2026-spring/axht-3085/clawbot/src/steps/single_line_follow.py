from dataclasses import dataclass
from libstp import *
from libstp.foundation import ChassisVelocity, PidConfig, PidController

@dataclass
class BetterSingleLineFollowConfig:
    """Configuration for single-sensor line following."""
    sensor: IRSensor
    forward_speed: float  # m/s
    distance_cm: float
    threshold: float = 0.5  # black confidence above this = on line
    rotation_gain: float = 0.25  # how much to rotate based on error
    strafe_gain: float = 0.05  # how much to strafe based on error
    follow_on_left_side: bool = True
@dsl(hidden=True)

class BetterSingleSensorLineFollow(MotionStep):
    """
    Follow a line using a single IR sensor.

    Uses the sensor's black confidence relative to a threshold to determine
    steering direction. Simpler than two-sensor following but less accurate.
    """

    def __init__(self, config: BetterSingleLineFollowConfig):
        super().__init__()
        self.config = config
        self._target_distance_m: float = 0.0

    def _generate_signature(self) -> str:
        return (
            f"SingleSensorLineFollow(distance={self.config.distance_cm:.1f}cm, "
            f"speed={self.config.forward_speed:.2f})"
        )

    def to_simulation_step(self) -> SimulationStep:
        base = super().to_simulation_step()
        distance_m = self.config.distance_cm / 100.0
        base.delta = SimulationStepDelta(
            forward=distance_m,
            strafe=0.0,
            angular=0.0,
        )
        return base

    def on_start(self, robot: "GenericRobot") -> None:
        self._target_distance_m = self.config.distance_cm / 100.0
        robot.odometry.reset()
        self._invert_correction = 1 if self.config.follow_on_left_side else -1

    def on_update(self, robot: "GenericRobot", dt: float) -> bool:
        # Check distance
        current_pose = robot.odometry.get_pose()
        traveled = abs(current_pose.position[0])  # x is forward
        if traveled >= self._target_distance_m:
            return True

        # Calculate error relative to threshold
        confidence = self.config.sensor.probabilityOfBlack()
        error = confidence - self.config.threshold

        # Apply gains
        rotation = self._invert_correction * self.config.rotation_gain * error
        strafe = self._invert_correction * -self.config.strafe_gain * error
        forward = self.config.forward_speed * abs(error)

        velocity = ChassisVelocity(forward, strafe, rotation)
        robot.drive.set_velocity(velocity)
        robot.drive.update(dt)
        return False


@dsl(tags=["motion", "line-follow"])
def follow_line_single_left_edge(
        sensor: IRSensor,
        distance_cm: float,
        forward_speed: float,
        threshold: float = 0.5,
        rotation_gain: float = 0.25,
        strafe_gain: float = 0.05,
) -> BetterSingleSensorLineFollow:
    """
    Follow a line using a single sensor for a specified distance.

    Args:
        sensor: The IR sensor instance
        distance_cm: Distance to follow in centimeters
        forward_speed: Forward speed in m/s
        threshold: Black confidence above this = on line
        rotation_gain: How much to rotate based on error
        strafe_gain: How much to strafe based on error

    Returns:
        SingleSensorLineFollow step
    """
    config = BetterSingleLineFollowConfig(
        sensor=sensor,
        forward_speed=forward_speed,
        distance_cm=distance_cm,
        threshold=threshold,
        rotation_gain=rotation_gain,
        strafe_gain=strafe_gain,
        follow_on_left_side = True,
    )
    return BetterSingleSensorLineFollow(config)

@dsl(tags=["motion", "line-follow"])
def follow_line_single_right_edge(
        sensor: IRSensor,
        distance_cm: float,
        forward_speed: float,
        threshold: float = 0.5,
        rotation_gain: float = 0.25,
        strafe_gain: float = 0.05,
) -> BetterSingleSensorLineFollow:
    """
    Follow a line using a single sensor for a specified distance.

    Args:
        sensor: The IR sensor instance
        distance_cm: Distance to follow in centimeters
        forward_speed: Forward speed in m/s
        threshold: Black confidence above this = on line
        rotation_gain: How much to rotate based on error
        strafe_gain: How much to strafe based on error

    Returns:
        SingleSensorLineFollow step
    """
    config = BetterSingleLineFollowConfig(
        sensor=sensor,
        forward_speed=forward_speed,
        distance_cm=distance_cm,
        threshold=threshold,
        rotation_gain=rotation_gain,
        strafe_gain=strafe_gain,
        follow_on_left_side = False,
    )
    return BetterSingleSensorLineFollow(config)
