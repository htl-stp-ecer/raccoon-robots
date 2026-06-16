from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import grab_brown_cube_start_pos
from src.steps.drive_to_analog_target_bidirectional import drive_to_analog_target_bidirectional


def left_lateral_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.RIGHT)
        .move(strafe=1)
        .correct_forward()
        .pid(kp=0.4, ki=0.05, kd=0.0)
    )

class M007MoveToCenterMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(origin_offset_deg=90),
            background(
                step=parallel(
                    grab_brown_cube_start_pos(),
                    Defs.arm_claw.idle(),# make sure claw is closed
                ),
                name="prep_arm"
            ),

            drive_forward(heading=-90).until(
                on_black(Defs.rear.left)
            ),

            # drive to line
            left_lateral_line_follow().until(
                after_cm(40)
            ),

            turn_to_heading_left(0),

            drive_backward(heading=0).until(
                on_black(Defs.rear.left)
            ),

        ])
