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
        speed=0.4,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.5,
        kd=0.05,
    )


class M040DropFirstCubeStack(Mission):
    def sequence(self) -> Sequential:
        return seq([
            background(
                step=arm.move_angles(
                    0, 110, -90
                ),
            ),

            # drive to external loading dock while rotating arm
            drive_backward(cm=20),  # make sure we never hit the upper warehous with something of the bot
            turn_left(180),
            strafe_right().until(
                on_black(Defs.rear.left)
            ),
            line_follow().until(
                after_cm(90)
            ),
            strafe_right().until(
                over_line(Defs.rear.left) | after_seconds(2)
            ),
            align_line_follow().until(
                after_seconds(0.4),
            ),
            mark_heading_reference(),

            # place cube tower
            drive_backward(cm=13),
            arm.move_angles(
                -3, 70, -70,
                speed=150
            ),
            Defs.arm_claw.open(),
        ])
