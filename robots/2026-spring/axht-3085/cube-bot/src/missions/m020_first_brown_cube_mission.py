from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import *

def forward_line_follow():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=1)
        .correct_lateral()
        .pid(kp=0.7, ki=0.3, kd=0.1)
    )

def backward_line_follow():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=-1)
        .correct_lateral()
        .pid(kp=0.7, ki=0.3, kd=0.1)
    )

class M020FirstBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # line follow backwards to retrieve spot
            drive_forward(heading=0).until(
                over_line(Defs.rear.left) #if we ever are over the line this conditio will fix it
                + after_cm(5)
            ),
            # go into correct lateral position for pickup
            strafe_right(heading=0, speed=0.5).until(
                on_black(Defs.rear.left),
            ),
            wait_for_background(
                name="prep_arm"
            ),

            grab_brown_cube(LineSide.LEFT, heading=0),

            # move away from shared warehouse
            timeout_or(
                strafe_left(heading=0).until(
                    on_black(Defs.front.left)
                    + after_cm(4)
                ),
                seconds=3,
                fallback=seq([
                    Defs.arm_claw.open(),
                    strafe_left(heading=0).until(
                        on_black(Defs.front.left)
                        + after_cm(4)
                    ),
                ]),
            ),

            background(
                step=drop_cube_into_container(),
                name="drop_cube"
            ),
        ])
