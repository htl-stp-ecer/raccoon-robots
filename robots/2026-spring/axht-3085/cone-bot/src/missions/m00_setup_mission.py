from libstp import *

from src.hardware.defs import Defs
from src.steps.cone_container_steps import down_cone_container, up_cone_container


class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            Defs.claw_servo.closed(),
            Defs.cone_arm_servo.up(),
            down_cone_container(),
            calibrate(distance_cm=50),
            up_cone_container(),
        ])
