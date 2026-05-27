from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import *


def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front_right_light_sensor,
        speed=-1,
        side=LineSide.LEFT,
        kp=0.8,
        ki=0.3,
        kd=0.2,
    )

class M010FirstBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),

            # align to black line linear
            drive_forward().until(
                on_black(Defs.front_right_light_sensor)
            ),
            drive_backward().until(
                on_white(Defs.front_right_light_sensor)
                + after_cm(1)
            ),

            # linefollow backwards to retrieve spot
            backward_line_follow().until(
                after_cm(12)
            ),

            grab_brown_cube(),

            arm.move_angles(0, 110, -120),       # rotate arm forward
            arm.move_angles(0, 65, 110),         # move arm to drop cube into container position
            Defs.arm_claw.full_open(),           # let go of cube
        ])
