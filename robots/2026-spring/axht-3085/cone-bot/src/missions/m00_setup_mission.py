from libstp import *

from src.hardware.defs import Defs


class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            motor_off(Defs.cone_container_motor),
            Defs.claw_servo.closed(),
            Defs.cone_arm_servo.up(),
            calibrate(distance_cm=50),
            loop_forever(
                seq([
                    wait_for_button(),
                    forward_single_lineup(
                        Defs.front.right,
                        entry_threshold=0.9,
                        exit_threshold=0.85,
                        correction_side=CorrectionSide.RIGHT,
                        forward_speed=0.5,
                    ),
                ])
            ),
            Defs.cone_arm_servo.down()
        ])
