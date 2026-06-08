from raccoon import *

from src.steps.line_follow_dsl import strafe_follow_line_single_free, strafe_follow_line_single
from src.kinematics.arm import arm
from src.hardware.defs import Defs


def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.rear.left,
        speed=1,
        side=LineSide.LEFT,
        kp=0.6,
        ki=0.5,
        kd=0.05,
    )


def align_line_follow():
    return strafe_follow_line_single_free(
        sensor=Defs.rear.left,
        speed=0.4,
        side=LineSide.LEFT,
        kp=0.6,
        ki=0.5,
        kd=0.05,
    )


class M040DropFirstCubeStack(Mission):
    def sequence(self) -> Sequential:
        return seq([
            background(
                step=seq([
                    wait_for_background("arm_up"),
                    arm.move_angles( #move servo forward
                        0, 110, -70, speed=150
                    ),
                ])
            ),

            # drive to external loading dock while rotating arm
            strafe_left(heading=0).until(
                on_black(Defs.rear.left)
            ),
            line_follow().until(
                after_cm(115)
            ),
            parallel(
                align_line_follow().until(
                    after_seconds(0.4),
                ),
                arm.move_angles(  # move servo forward
                    85, 70, -30, speed=150
                ),
            ),
            mark_heading_reference(),
            arm.move_angles(93, 75, -55, speed=150),

            # place cube tower
            Defs.arm_claw.open(),
            wait_for_button(),
        ])
