from raccoon import *

from src.hardware.defs import Defs


@dsl
def drive_to_second_pipe():
    def line_follower():
        return follow_line_single(
            Defs.front_right_ir_sensor,
            speed=1.0,
            kp=0.7,
            ki=0.2,
            kd=0.1,
            side=LineSide.LEFT,
        )

    return seq([
        line_follower().until(
            after_cm(20) +
            on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor),
        ),

        # make sure we are straight (to drive accurace distance
        turn_to_heading_right(90),
        #turn_right().until(on_black(Defs.front_right_ir_sensor)), #turn until right sensor is on black to start linefollowing

        # TODO: Try a drive straight and align on pipe
        drive_forward(cm=41),
        #line_follower().until(
        #    after_forward_cm(43)
        #),
    ])
