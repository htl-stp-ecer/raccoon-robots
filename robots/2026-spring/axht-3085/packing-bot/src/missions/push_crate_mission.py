from libstp import *

from src.hardware.defs import Defs
from src.steps.servo_steps import servo_pom_arm_up


class PushCrateMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            servo_pom_arm_up(),
            strafe_until_black(sensor=Defs.front_left_light_sensor, strafe_speed=1.0, confidence_threshold=0.4),
            #strafe_until_white(sensor=Defs.front_left_light_sensor, strafe_speed=1.0),
            strafe_right(cm=10, speed = 1.0),
            wait(1),
            drive_forward(40.0, speed=1.0),
            drive_backward(10.0, speed=1.0),
        ])
