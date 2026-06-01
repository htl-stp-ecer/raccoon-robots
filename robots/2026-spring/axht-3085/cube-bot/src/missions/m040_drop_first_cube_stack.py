from raccoon import *

from src.steps.line_follow_dsl import strafe_follow_line_single_free, strafe_follow_line_single
from src.kinematics.arm import arm
from src.hardware.defs import Defs

def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.rear.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.5,
        kd=0.05,
    )

def align_line_follow():
    return strafe_follow_line_single_free(
        sensor=Defs.rear.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.5,
        kd=0.05,
    )


class M040DropFirstCubeStack(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # turn around
            turn_to_heading_left(0, force_direction='left'),

            # drive to external loading dock while rotating arm
            parallel(
                seq([
                    line_follow().until(
                        after_cm(105)
                    ),
                    align_line_follow().until(
                        after_seconds(0.7),
                    ),
                ]),
                arm.move_angles(
                    0, 110, -90
                ),
            ),
            turn_to_heading_left(0),

            # place cube tower
            arm.move_angles(7, 135, -135),
            servo(Defs.arm_elbow, -28),
            Defs.arm_claw.full_open(),
        ])