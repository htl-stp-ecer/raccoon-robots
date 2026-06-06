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
            background( # make sure claw is closed
                step=Defs.arm_claw.idle(),
            ),

            # align to black line linear
            forward_line_follow().until(
                on_black(Defs.front.right)
            ),

            # line follow backwards to retrieve spot
            background(
                step= grab_brown_cube_start_pos(),
                name="prep_arm"
            ),
            backward_line_follow().until(
                on_white(Defs.front.left)
                + after_cm(13)
            ),
            # go into correct lateral position for pickup
            strafe_left(heading=180).until(
                on_black(Defs.front.right),
            ),
            wait_for_background(
                name="prep_arm"
            ),

            grab_brown_cube(LineSide.LEFT, heading=180),

            # move away from shared warehouse
            strafe_right(heading=180).until(
                on_black(Defs.front_left_light_sensor)
            ),

            background(
                step=drop_cube_into_container(),
                name="drop_cube"
            ),
        ])
