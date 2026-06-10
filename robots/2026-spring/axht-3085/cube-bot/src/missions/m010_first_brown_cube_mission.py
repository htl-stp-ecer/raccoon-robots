from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import *

def forward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.7,
        ki=0.3,
        kd=0.1,
    )

def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.left,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.7,
        ki=0.3,
        kd=0.1,
    )

class M010FirstBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # line follow backwards to retrieve spot
            background(
                step=parallel(
                    grab_brown_cube_start_pos(),
                    Defs.arm_claw.idle(),# make sure claw is closed
                ),
                name="prep_arm"
            ),
            drive_forward().until(
                over_line(Defs.rear.left) #if we ever are over the line this conditio will fix it
                + after_cm(7)
            ),
            # go into correct lateral position for pickup
            strafe_right(heading=0).until(
                on_black(Defs.rear.left),
            ),
            wait_for_background(
                name="prep_arm"
            ),

            grab_brown_cube(LineSide.LEFT, heading=0),
            turn_to_heading_right(0),

            # move away from shared warehouse
            strafe_left(heading=0).until(
                over_line(Defs.front.left)
            ),

            background(
                step=drop_cube_into_container(),
                name="drop_cube"
            ),
        ])
