from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import *


def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front_right_light_sensor,
        speed=-1,
        side=LineSide.LEFT,
        kp=0.7,
        ki=0.3,
        kd=0.1,
    )

class M010FirstBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(origin_offset_deg=180),

            # align to black line linear
            drive_forward(heading=180).until(
                on_black(Defs.front_right_light_sensor)
            ),
            drive_backward(heading=180).until(
                on_white(Defs.front_right_light_sensor)
                + after_cm(1)
            ),

            # line follow backwards to retrieve spot
            backward_line_follow().until(
                after_cm(12)
            ),

            grab_brown_cube(),

            # move away from shared warehouse
            strafe_right(heading=180).until(
                on_black(Defs.front_left_light_sensor)
            ),

            drop_cube_into_container(),
        ])
