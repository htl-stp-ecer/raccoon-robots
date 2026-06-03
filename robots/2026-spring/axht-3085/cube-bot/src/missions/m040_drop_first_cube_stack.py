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
            # drive to external loading dock while rotating arm
            parallel(
                seq([
                    drive_backward(cm=15),  # make sure we never hit the upper warehous with something of the bot
                    turn_left(180),
                    strafe_right().until(
                        on_black(Defs.rear.left)
                    ),
                    line_follow().until(
                        after_cm(95)
                    ),
                    strafe_right().until(
                        over_line(Defs.rear.left),
                    ),
                    align_line_follow().until(
                        after_seconds(0.4),
                    ),
                    mark_heading_reference()
                ]),
                arm.move_angles(
                    0, 110, -90
                ),
            ),

            # place cube tower
            arm.move_angles(15, 130, -130, speed=180),
            servo(Defs.arm_elbow, -28),
            Defs.arm_claw.open(),
        ])