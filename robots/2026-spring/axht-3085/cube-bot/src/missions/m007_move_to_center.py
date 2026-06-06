from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.drive_to_analog_target_bidirectional import drive_to_analog_target_bidirectional
from src.steps.line_follow_dsl import lateral_follow_line_single_free, lateral_follow_line_single


def left_lateral_line_follow():
    return lateral_follow_line_single(
        sensor=Defs.front.right,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.05,
        kd=0.0,
    )

def pipe_align():
    return lateral_follow_line_single_free(
        sensor=Defs.front.right,
        speed=0.6,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.0,
    )


class M007MoveToCenter(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(origin_offset_deg=90),
            drive_forward().until(
                over_line(Defs.rear.left)
                + (on_black(Defs.front.right) | on_black(Defs.front.left))
            ),

            # drive to line
            left_lateral_line_follow().until(
                after_cm(40)
            ),

            turn_to_heading_left(0),

            drive_backward().until(
                on_black(Defs.rear.left)
            )

        ])
