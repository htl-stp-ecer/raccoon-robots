from raccoon import *
from src.hardware.defs import Defs
from src.steps.line_follow_dsl import *
from src.kinematics.arm import arm
from src.steps.arm_steps import *


def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
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
                    wait_for(
                        over_line(Defs.rear.left) | after_seconds(2),
                    ),
                    grab_brown_cube_start_pos()
                ]),

                # drive forward to 2nd cube pickup
                seq([
                    line_follow().until(
                        over_line(Defs.rear.left)
                        + after_cm(15)
                    ),
                ]),
            ),

            # go into correct lateral position for pickup
            strafe_left(heading=180).until(
                on_black(Defs.front.right),
            ),
            # dont strafe back to white so the arm reaches te cube better
            # strafe_right(heading=180, speed=0.2).until(
            #    on_white(Defs.front.right),
            # ),

            grab_brown_cube(LineSide.RIGHT, heading=180),
        ])
