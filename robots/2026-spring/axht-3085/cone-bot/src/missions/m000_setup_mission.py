from libstp import *

from src.hardware.defs import Defs


class M000SetupMission(SetupMission):
    def sequence(self) -> Sequential:
        return seq([
            motor_off(Defs.cone_container_motor),
            Defs.claw_servo.closed(),
            Defs.cone_arm_servo.container_pos(),
            calibrate(distance_cm=50),

            Defs.cone_arm_servo.handl_hight(),

            Defs.cone_arm_servo.down()
        ])
