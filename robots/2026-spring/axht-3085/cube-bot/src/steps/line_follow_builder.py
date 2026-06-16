from __future__ import annotations

from enum import Enum

from raccoon.sensor_ir import IRSensor
from raccoon.step.annotation import dsl
from raccoon.step.condition import StopCondition
from raccoon.step.step_builder import StepBuilder

from .line_follow import (
    DirectionalLineFollow,
    DirectionalLineFollowConfig,
    DirectionalSingleLineFollow,
    DirectionalSingleLineFollowConfig,
    LineSide,
)

_UNSET = object()


class FollowCorrection(str, Enum):
    ANGULAR = "angular"
    LATERAL = "lateral"
    FORWARD = "forward"


class SensorFrame(str, Enum):
    ROBOT = "robot"
    TRAVEL = "travel"


def _travel_relative_side(side: LineSide, strafe_speed: float) -> LineSide:
    is_right = side == LineSide.RIGHT
    if strafe_speed >= 0.0:
        return LineSide.LEFT if is_right else LineSide.RIGHT
    return LineSide.RIGHT if is_right else LineSide.LEFT


class ConfigurableLineFollowBuilder(StepBuilder):
    """Single configurable builder for directional line following.

    This collapses the named variants down to the actual degrees of freedom:

    - tracking: one sensor edge or two-sensor centered
    - motion: heading + strafe base velocities
    - correction: angular, lateral, or forward
    - heading hold: on/off for translation-based correction
    - sensor interpretation: robot-relative or travel-relative

    Examples:

        line_follow()
            .single(Defs.front.left, side=LineSide.RIGHT)
            .move(heading=1.0)
            .correct_lateral()
            .pid(kp=0.7, ki=0.3, kd=0.1)
            .until(after_cm(120))

        line_follow()
            .single(Defs.rear.left, side=LineSide.LEFT)
            .move(heading=0.4)
            .correct_lateral(hold_heading=False)
            .pid(kp=0.6, ki=0.3, kd=0.0)
            .until(after_seconds(0.4))

        line_follow()
            .dual(Defs.front.left, Defs.front.right)
            .move(strafe=0.7)
            .relative_to_travel()
            .correct_forward()
            .pid(kp=0.5, ki=0.1, kd=0.0)
            .until(after_cm(80))
    """

    def __init__(self) -> None:
        super().__init__()
        self._left_sensor = _UNSET
        self._right_sensor = _UNSET
        self._sensor = _UNSET
        self._side = LineSide.LEFT
        self._heading_speed = 0.0
        self._strafe_speed = 0.0
        self._distance_cm: float | None = None
        self._kp = 0.4
        self._ki = 0.0
        self._kd = 0.1
        self._until: StopCondition | None = None
        self._correction = FollowCorrection.ANGULAR
        self._heading_hold = True
        self._sensor_frame = SensorFrame.ROBOT
        self._correction_sign = 1.0

    def dual(self, left_sensor: IRSensor, right_sensor: IRSensor) -> ConfigurableLineFollowBuilder:
        self._left_sensor = left_sensor
        self._right_sensor = right_sensor
        self._sensor = _UNSET
        return self

    def single(
        self,
        sensor: IRSensor,
        side: LineSide = LineSide.LEFT,
    ) -> ConfigurableLineFollowBuilder:
        self._sensor = sensor
        self._side = side
        self._left_sensor = _UNSET
        self._right_sensor = _UNSET
        return self

    def move(
        self,
        heading: float = 0.0,
        strafe: float = 0.0,
    ) -> ConfigurableLineFollowBuilder:
        self._heading_speed = heading
        self._strafe_speed = strafe
        return self

    def heading_speed(self, value: float) -> ConfigurableLineFollowBuilder:
        self._heading_speed = value
        return self

    def strafe_speed(self, value: float) -> ConfigurableLineFollowBuilder:
        self._strafe_speed = value
        return self

    def correct_angular(self) -> ConfigurableLineFollowBuilder:
        self._correction = FollowCorrection.ANGULAR
        self._heading_hold = True
        return self

    def correct_lateral(self, hold_heading: bool = True) -> ConfigurableLineFollowBuilder:
        self._correction = FollowCorrection.LATERAL
        self._heading_hold = hold_heading
        return self

    def correct_forward(self, hold_heading: bool = True) -> ConfigurableLineFollowBuilder:
        self._correction = FollowCorrection.FORWARD
        self._heading_hold = hold_heading
        return self

    def relative_to_robot(self) -> ConfigurableLineFollowBuilder:
        self._sensor_frame = SensorFrame.ROBOT
        return self

    def relative_to_travel(self) -> ConfigurableLineFollowBuilder:
        self._sensor_frame = SensorFrame.TRAVEL
        return self

    def correction_sign(self, value: float) -> ConfigurableLineFollowBuilder:
        self._correction_sign = value
        return self

    def distance_cm(self, value: float | None) -> ConfigurableLineFollowBuilder:
        self._distance_cm = value
        return self

    def pid(self, kp: float, ki: float = 0.0, kd: float = 0.1) -> ConfigurableLineFollowBuilder:
        self._kp = kp
        self._ki = ki
        self._kd = kd
        return self

    def kp(self, value: float) -> ConfigurableLineFollowBuilder:
        self._kp = value
        return self

    def ki(self, value: float) -> ConfigurableLineFollowBuilder:
        self._ki = value
        return self

    def kd(self, value: float) -> ConfigurableLineFollowBuilder:
        self._kd = value
        return self

    def until(self, value: StopCondition | None) -> ConfigurableLineFollowBuilder:
        self._until = value
        return self

    def _build(self):
        if self._distance_cm is None and self._until is None:
            msg = "line_follow() requires either distance_cm(...) or until(...)"
            raise ValueError(msg)

        has_pair = self._left_sensor is not _UNSET or self._right_sensor is not _UNSET
        has_single = self._sensor is not _UNSET
        if has_pair == has_single:
            msg = "line_follow() requires exactly one tracking mode: single(...) or dual(...)"
            raise ValueError(msg)
        if has_pair and (self._left_sensor is _UNSET or self._right_sensor is _UNSET):
            msg = "dual(...) requires both left and right sensors"
            raise ValueError(msg)

        forward_correction = self._correction == FollowCorrection.FORWARD
        lateral_correction = self._correction == FollowCorrection.LATERAL

        if lateral_correction and self._strafe_speed != 0.0:
            msg = "lateral correction already uses strafe for correction; base strafe_speed must stay 0"
            raise ValueError(msg)
        if forward_correction and self._heading_speed != 0.0:
            msg = "forward correction already uses heading for correction; base heading_speed must stay 0"
            raise ValueError(msg)
        if self._correction == FollowCorrection.ANGULAR and not (self._heading_speed or self._strafe_speed):
            msg = "angular correction needs a non-zero base motion"
            raise ValueError(msg)
        if self._sensor_frame == SensorFrame.TRAVEL and not forward_correction:
            msg = "relative_to_travel() only applies to lateral travel with forward correction"
            raise ValueError(msg)
        if self._sensor_frame == SensorFrame.TRAVEL and self._strafe_speed == 0.0:
            msg = "relative_to_travel() requires non-zero strafe_speed"
            raise ValueError(msg)

        if has_single:
            side = self._side
            if self._sensor_frame == SensorFrame.TRAVEL:
                side = _travel_relative_side(side, self._strafe_speed)
            config = DirectionalSingleLineFollowConfig(
                sensor=self._sensor,
                heading_speed=self._heading_speed,
                strafe_speed=self._strafe_speed,
                distance_cm=self._distance_cm,
                side=side,
                kp=self._kp,
                ki=self._ki,
                kd=self._kd,
                lateral_correction=lateral_correction,
                forward_correction=forward_correction,
                heading_hold=self._heading_hold,
                correction_sign=self._correction_sign,
            )
            return DirectionalSingleLineFollow(config, until=self._until)

        left_sensor = self._left_sensor
        right_sensor = self._right_sensor
        if self._sensor_frame == SensorFrame.TRAVEL and self._strafe_speed >= 0.0:
            left_sensor, right_sensor = right_sensor, left_sensor

        config = DirectionalLineFollowConfig(
            left_sensor=left_sensor,
            right_sensor=right_sensor,
            heading_speed=self._heading_speed,
            strafe_speed=self._strafe_speed,
            distance_cm=self._distance_cm,
            kp=self._kp,
            ki=self._ki,
            kd=self._kd,
            lateral_correction=lateral_correction,
            forward_correction=forward_correction,
            correction_sign=self._correction_sign,
        )
        return DirectionalLineFollow(config, until=self._until)


@dsl(tags=["motion", "line-follow"])
def line_follow() -> ConfigurableLineFollowBuilder:
    """Create a configurable builder for directional line following."""
    return ConfigurableLineFollowBuilder()


__all__ = [
    "ConfigurableLineFollowBuilder",
    "FollowCorrection",
    "SensorFrame",
    "line_follow",
]
