from libstp import *

from src.hardware.defs import Defs


class M025CollectSecondConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #drive to second cone
            drive_forward().until(
                on_black(Defs.front_right_ir_sensor) >
                after_cm(10) >
                on_black(Defs.front_right_ir_sensor)
            ),

            drive_backward(15),
            turn_to_heading_right(70),

            # grab cone
            parallel(
                Defs.claw_servo.open(),
                Defs.cone_arm_servo.down(100),
            ),
            Defs.claw_servo.closed(120),

            # drop cone into container
            parallel(
                seq([
                    Defs.cone_arm_servo.container_pos(140),
                    Defs.claw_servo.half_open(100),
                    Defs.claw_servo.closed(100),
                ]),
                turn_to_heading_right(90),
            )
        ])