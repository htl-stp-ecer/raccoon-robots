from src.kinematics.arm import arm
from raccoon import *


def arm_grab_basket():
    return seq([
        #drive over basket
        arm.move_angles(115, 82, -45),
        wait_for_seconds(0.5),
        #move down
        arm.move_angles(115, 82, -90),
        wait_for_seconds(0.5),
        #move to the side under holder
        arm.move_angles(128, 82, -90),
        wait_for_seconds(0.5),

        #move arm up
        arm.move_angles(128, 90, -45),
    ])