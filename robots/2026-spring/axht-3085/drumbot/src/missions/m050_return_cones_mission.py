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

            optimize([
                # scoop cones into pusher
                drive_backward().until(
                    over_line(Defs.front_right_ir_sensor)
                    + after_cm(4)
                ),

                turn_to_heading_right(90),
            ]).cut_corners(10),

            # start driving to lower starting box
            line_follow()
            .single(Defs.rear_left_ir_sensor, LineSide.RIGHT)
            .move(forward=-1)
            .correct_angular()
            .pid(1.0, 0.2, 0.1)
            .until(
                over_line(Defs.front_right_ir_sensor)
                + on_black(Defs.front_right_ir_sensor)
            ),

            optimize([
                turn_to_heading_right(70),
                drive_backward(cm=45, heading=-70),
                turn_to_heading_right(45),
                drive_backward(cm=40, heading=-45),
            ]).cut_corners(10),
        ])
