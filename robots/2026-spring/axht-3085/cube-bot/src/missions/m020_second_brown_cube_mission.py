from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import *


def _follow():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=-1)
        .correct_lateral()
        .pid(kp=0.6, ki=0.3, kd=0.05)
    )


class M020SecondBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                # start moving arm by 90° as soon as black line was crossed
                seq([
                    wait_for_background(name="drop_cube"),
                    arm.move_angles(0, 65, 0, speed=150),
                    Defs.arm_claw.idle(),
                    grab_brown_cube_start_pos()
                ]),

                # drive backwards to 2nd cube pickup
                seq([
                    _follow().until(
                        (over_line(Defs.front.right)
                        + after_cm(20))
                        | after_seconds(6)
                    ),
                ]),
            ),
            # go into correct lateral position for pickup
            strafe_right(heading=0).until(
                on_black(Defs.rear.left),
            ),

            grab_brown_cube(LineSide.RIGHT, heading=0),
            turn_to_heading_right(0),
        ])
