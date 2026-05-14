from src.hardware.defs import Defs
from src.kinematics.arm import arm
from raccoon import *


def drop_cone_into_holder(base_angle: float):
    return seq([
        # drop cone
        arm.move_angles(base_angle, 100, 80),
        wait_for_seconds(0.1),
        Defs.arm_claw.p45deg(),
    ])


def arm_grab_basket():
    return seq([
        # drive over basket
        arm.move_angles(115, 82, -45),
        wait_for_seconds(0.1),

        # move down
        arm.move_angles(115, 82, -100),
        wait_for_seconds(0.2),

        # move to the side under holder
        arm.move_angles(128, 82, -100),
        wait_for_seconds(0.2),

        # move arm up
        arm.move_angles(128, 90, -45),
    ])

def return_tray_to_tray_holder_phase1():
    return seq([
        arm.move_angles(-90, 90, -100),            # go to 90-90 so the arm can lift the tray
        arm.move_angles(-90, 90, -50),             # lift the tray (hopefully)
    ])

def return_tray_to_tray_holder_phase2():
    return seq([
        arm.move_angles(115, 90, -50, speed=100),  # move over tray holder
        arm.move_angles(115, 90, -100, speed=60),  # place tray down
        arm.move_angles(140, 90, -100, speed=70),  # move it back so it sits fully on the tray holder

        arm.move_angles(110, 90, -100),
        arm.move_angles(110, 90, 0),
        arm.move_angles(0, 90, 0),
    ])