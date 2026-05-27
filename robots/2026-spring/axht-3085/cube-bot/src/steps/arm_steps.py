from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm

def grab_brown_cube():
    return seq([
        arm.move_angles(-90, 110, -120),     # rotate left to face correct direction
        arm.move_angles(-90, 80, -75),       # move into shared area
        arm.move_angles(-90, 60, -40),       # move further into shared area
        Defs.arm_claw.full_open(),           # open claw
        arm.move_angles(-90, 30, -35),       # move down
        Defs.arm_claw.grab(),                # grab cube

        arm.move_angles(-90, 60, -40),       # lift cube up
        background(
            arm.move_angles(-90, 110, -120),     # move out of shared area
        ),

        # move away from shared warehouse
        strafe_right().until(
            on_black(Defs.front_left_light_sensor)
        ),
    ])