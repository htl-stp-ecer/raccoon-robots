from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import grab_right_brown_cube_start_pos


def left_lateral_line_follow():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(strafe=1)
        .correct_forward()
        .hold_heading(-90)
        .pid(kp=0.4, ki=0.05, kd=0.0)
    )


class M010MoveToCenterMission(Mission):
    def sequence(self) -> Step:
        return optimize([
            mark_heading_reference(origin_offset_deg=-90),
            optimize([
                drive_backward(cm=10),
                spline((-20, 0),(-40, 70), absolute_heading=True,final_heading=0, speed=1),
                background(
                    grab_right_brown_cube_start_pos(),
                ),
                drive_backward(heading=0).until(
                    on_black(Defs.rear.left)
                ),
            ]),
        ])
