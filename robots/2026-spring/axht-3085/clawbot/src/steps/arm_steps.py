from src.hardware.defs import Defs
from src.kinematics.arm import arm
from raccoon import *


def arm_grab_basket():
    return seq([
        #drive over basket
        arm.move_angles(115, 82, -45),
        wait_for_seconds(0.2),
        #move down
        arm.move_angles(115, 82, -90),
        wait_for_seconds(0.3),
        #move to the side under holder
        arm.move_angles(128, 82, -90),
        wait_for_seconds(0.3),

        #move arm up
        arm.move_angles(128, 90, -45),
    ])

def drop_cone_into_holder(base_angle: float):
    return seq([
        #drop cone
        arm.move_angles(base_angle, 90, 91),
        wait_for_seconds(0.2),
        Defs.arm_claw.p45deg(),

    ])