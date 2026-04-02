from libstp import *

from src.hardware.defs import Defs


class M020CollectConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #position to grab cone
            drive_backward(15),
            turn_to_heading_right(70),

            #grab cone
            parallel(
                Defs.claw_servo.open(),
                Defs.cone_arm_servo.down(100),
            ),
            Defs.claw_servo.closed(120),

            #drop cone into container
            parallel(
                seq([
                    Defs.cone_arm_servo.container_pos(140),
                    Defs.claw_servo.half_open(100),
                ]),
                turn_to_heading_right(90),
            ),
        ])