from raccoon import *

from src.hardware.defs import Defs


@dsl
def drive_to_second_pipe():
    return seq([
        parallel(
            follow_line_single(
                Defs.front_right_ir_sensor,
                kp=0.5,
                kd=0.1,
                side=LineSide.LEFT,
            ).until(
                on_black(Defs.front_left_ir_sensor)
            ),

            #make sure we are straight (to drive accurace distance
            turn_to_heading_right(180),

            #TODO: Try a drive straight and align on pipe
            follow_line_single(
                Defs.front_right_ir_sensor,
                kp=0.5,
                kd=0.1,
                side=LineSide.LEFT,
            ).until(
                after_forward_cm(43)
            ),
        )
    ])
