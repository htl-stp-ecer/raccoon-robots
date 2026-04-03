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
            Defs.claw_servo.closed(150),

            #drop cone into container
            parallel(
                seq([
                    Defs.cone_arm_servo.container_pos(200),
                    wait_for_seconds(0.2), #wat a bit so the servo is actually up!
                    Defs.claw_servo.half_open(),
                ]),
                turn_to_heading_right(90),
            )
        ])