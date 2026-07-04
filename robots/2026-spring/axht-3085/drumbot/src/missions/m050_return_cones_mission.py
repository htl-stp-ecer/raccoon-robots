from raccoon import *
from src.hardware.defs import Defs
from src.steps.cone_pusher_steps import lower_cone_pusher

class M050ReturnConesMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # turn away and tuck in drum while lowering cone pusher
            parallel(
                turn_left(53),
                seq([
                    wait_for_seconds(0.2),
                    Defs.lift_drums_servo.over_limit(120),
                ]),
            ),

            lower_cone_pusher(),

            # scoop cones into pusher
            drive_backward().until(
                over_line(Defs.front_right_ir_sensor)
                + after_cm(4)
            ),

            turn_to_heading_right(90),

            # start driving to lower starting box
            line_follow()
            .single(Defs.rear_left_ir_sensor, LineSide.RIGHT)
            .move(forward=-1)
            .correct_angular()
            .pid(1.5, 0.3, 0.1)
            .until(
                over_line(Defs.front_right_ir_sensor)
                + over_line(Defs.front_right_ir_sensor)
            ),

            drive_arc_left(
                radius_cm=50,
                degrees=55
            ),
            drive_forward(20),


        ])
