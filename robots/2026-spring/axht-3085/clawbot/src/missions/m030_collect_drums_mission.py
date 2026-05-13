from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import arm_grab_basket


def line_follow():
    return strafe_follow_line_single(
        Defs.front.right,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.2,
        kd=0.0,
    )


def backward_line_follow():
    return strafe_follow_line_single(
        Defs.front.right,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.2,
        kd=0.0,
    )


class M030CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                seq([
                    turn_to_heading_left(0),
                    strafe_left().until(
                        over_line(Defs.front.right)
                    ),
                    turn_to_heading_left(0),
                ]),
                seq([
                    wait_for_background("drop_cone"),
                    arm_grab_basket(),
                    arm.move_angles(-90, 90, -45),
                    arm.move_angles(-90, 40, 0),
                ]),
            ),

            line_follow().until(
                over_line(Defs.rear.left)
                + after_cm(15)
            ),

            wait_for_checkpoint(70),
            arm.move_angles(-90, 40, -10),

            background(
                seq([
                    wait_for(on_black(Defs.rear.left)),
                    arm.move_angles(-90, 45, -80),
                ]),
            ),
            backward_line_follow().until(
                over_line(Defs.rear.left)
                + over_line(Defs.front.left)
                + after_cm(10)
            ),
        ])
