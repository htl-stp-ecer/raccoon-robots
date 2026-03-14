from libstp import *

from src.hardware.defs import Defs


class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            motor_off(Defs.cone_container_motor),
            Defs.claw_servo.closed(),
            Defs.cone_arm_servo.up(),
            calibrate(distance_cm=50),
            # Defs.cone_arm_servo.down()
            # auto_tune(
            #     vel_axes=["vx", "wz"],
            #     characterize_axes=["forward", "angular"],
            #     motion_axes=["distance", "heading"],
            # ),
        ])
