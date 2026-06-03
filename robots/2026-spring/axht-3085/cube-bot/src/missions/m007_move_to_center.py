from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.drive_to_analog_target_bidirectional import drive_to_analog_target_bidirectional
from src.steps.line_follow_dsl import lateral_follow_line_single_free, lateral_follow_line_single


def left_lateral_line_follow():
    return lateral_follow_line_single(
        sensor=Defs.front.right,
        speed=-1,
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
            pipe_align().until(
                after_seconds(0.8)
            ),
            mark_heading_reference(origin_offset_deg=180),

            # align to drop green cube
            left_lateral_line_follow().until(
                on_black(Defs.rear.left)
            ),
            strafe_right(heading=180, speed=0.4).until(
               on_white(Defs.rear.left)
            ),

            # drop green cube
            arm.move_angles(0, 60, -66).arm_speeds(sholder=100),
            Defs.arm_claw.open(80),
            arm.move_angles(0, 100, -62),

            # drive to line
            left_lateral_line_follow().until(
                over_line(Defs.rear.left)
                + after_cm(23)
            ),
            drive_angle(angle_deg=-60).until(
                over_line(Defs.rear.left)
                + on_black(Defs.front.right)
            ),
        ])
