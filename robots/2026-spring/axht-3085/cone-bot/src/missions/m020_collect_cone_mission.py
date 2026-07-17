from raccoon import *

from src.hardware.defs import Defs


class M020CollectConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # position to grab cone
            drive_backward(15),
            parallel(
                Defs.claw_servo.open(),
                turn_to_heading_right(60),
            ),

            # grab cone
            Defs.cone_arm_servo.down(100),
            drive_forward(cm=15),
            Defs.claw_servo.closed(),

            # drop cone into container
            Defs.cone_arm_servo.container_pos(200),
            wait_for_seconds(0.2),  # wat a bit so the servo is actually up!
            Defs.claw_servo.half_open(),
            drive_backward(cm=15),
            turn_to_heading_right(90),
        ])
