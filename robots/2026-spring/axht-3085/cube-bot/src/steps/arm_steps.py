from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm

def grab_brown_cube():
    return seq([
        arm.move_angles(-90, 110, -120),      # rotate left to face correct direction
        arm.move_angles(-90, 80, -75)
            .arm_speeds(base=999, sholder=100, elbow=200),        # move into shared area
        arm.move_angles(-90, 60, -40)
            .arm_speeds(base=999, sholder=100, elbow=200),        # move further into shared area
        Defs.arm_claw.full_open(),            # open claw
        arm.move_angles(-90, 20, -25),        # move down
        Defs.arm_claw.grab(),                 # grab cube
        arm.move_angles(-90, 60, -50),        # lift cube up
        background(
            arm.move_angles(-90, 110, -120),  # move out of shared area
        ),
    ])

def drop_cube_into_container():
    return seq([
        #arm.move_angles(0, 110, -120),        # rotate arm forward
        arm.move_angles(0, 65, 110).arm_speeds(9999, 100, 150),          # move arm to drop cube into container position
        Defs.arm_claw.full_open(),            # let go of cube
    ])

def grab_cube_from_container():
    return seq([
        arm.move_angles(0, 110, -120),        # rotate arm forward
        Defs.arm_claw.full_open(),            # open claw
        arm.move_angles(0, 65, 110),          # move arm to drop cube into container position
        Defs.arm_claw.grab(),                 # let go of cube
    ])