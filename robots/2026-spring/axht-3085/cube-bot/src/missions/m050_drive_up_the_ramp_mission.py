from raccoon import *

from src.hardware.defs import Defs
from src.steps.line_follow_dsl import lateral_follow_line_single_free, lateral_follow_line_single


def left_lateral_line_follow():
    return lateral_follow_line_single(
        sensor=Defs.rear.left,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.05,
        kd=0.0,
    )

def right_lateral_line_follow():
    return lateral_follow_line_single_free(
        sensor=Defs.front.right,
        speed=1,
        side=LineSide.LEFT,
        kp=0.4,
        ki=0.05,
        kd=0.0,
    )

def forward_line_follow():
    return strafe_follow_line_single(
        Defs.front_left_light_sensor,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.3,
        kd=0.0,
    )

class M050DriveUpTheRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # drive back to starting box
            left_lateral_line_follow().until(
                after_cm(90)
            ),
            turn_to_heading_left(0),

            strafe_right().until(
                over_line(Defs.rear.left)
                + on_black(Defs.rear.left)
            ),

            drive_forward().until(
                on_black(Defs.front.right)
            ),

            # align on pipe
            right_lateral_line_follow().until(
                after_cm(25)
            ),

            # drive the up the ramp
            switch_calibration_set("upper"),
            forward_line_follow().until(
                after_cm(130)
                + over_line(Defs.front.right)
            )
        ])