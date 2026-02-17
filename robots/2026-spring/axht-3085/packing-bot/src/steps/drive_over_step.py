from dataclasses import dataclass
from libstp import *
from typing import *

from src.hardware.defs import *


@dataclass
class AdvancedMoveUntilConfig:
    """Configuration for MoveUntil step."""
    sensors: List[IRSensor]
    target: SurfaceColor
    forward_speed: float = 0.0  # m/s, positive = forward
    angular_speed: float = 0.0  # rad/s, positive = CCW
    strafe_speed: float = 0.0  # m/s, positive = left
    confidence_threshold: float = 0.7
    scale_speed_on_approach: bool = True  # slow down as we approach target


class AdvancedMoveUntil(MoveUntil):

    def __init__(self, config: AdvancedMoveUntilConfig):
        super().__init__(MoveUntilConfig(forward))
        self.config = config

    def _is_condition_met(self) -> bool:
        for sensor in self.config.sensor:
            """Check if the sensor has detected the target color."""
            if self.config.target == SurfaceColor.BLACK:
                confidence = sensor.probabilityOfBlack()
            else:
                confidence = sensor.probabilityOfWhite()
            if confidence >= self.config.confidence_threshold:
                return True

        return False


def frontside_forward_move_over_line(forward_speed: float, confidence_threshold: float = 0.7) -> Step:
    return seq([
        AdvancedMoveUntil(
            AdvancedMoveUntilConfig(
                sensors=[Defs.front_left_light_sensor, Defs.front_right_light_sensor],
                target=SurfaceColor.BLACK,
                forward_speed=forward_speed,
                confidence_threshold=confidence_threshold,
            )
        ),

        AdvancedMoveUntil(
            AdvancedMoveUntilConfig(
                sensors=[Defs.front_left_light_sensor, Defs.front_right_light_sensor],
                target=SurfaceColor.WHITE,
                forward_speed=forward_speed,
                confidence_threshold=confidence_threshold,
            )
        ),
    ])
