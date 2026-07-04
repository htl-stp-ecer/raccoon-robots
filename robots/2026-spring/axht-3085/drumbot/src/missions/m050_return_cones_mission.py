from raccoon import *
from src.hardware.defs import Defs
from src.steps.cone_pusher_steps import lower_cone_pusher

class M050ReturnConesMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # turn away and tuck in drum while lowering cone pusher
            parallel(
                turn_left(45),
                seq([
                    wait_for_seconds(0.2),
                    parallel(
                        Defs.lift_drums_servo.over_limit(120),
                        lower_cone_pusher(),
                    ),
                ]),
            ),

            drive_backward(speed=0.7).until(
                over_line(Defs.front_right_ir_sensor)
                + after_cm(4)
            ),

            turn_to_heading_right(90),
        ])
