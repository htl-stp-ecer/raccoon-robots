from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm

def drop_cone_into_holder(base_angle: float):
    return seq([
        # drop cone
        arm.move_angles(base_angle, 90, 65),
        Defs.arm_claw.p135deg(),
    ])


def arm_grab_tray():
    return seq([
        # drive over basket and close claw
        parallel(
            arm.move_angles(115, 82, -45),
            Defs.arm_claw.closed(),
        ),

        arm.move_angles(115, 90, -102),    # move down
        arm.move_angles(128, 90, -102),    # move to the side under holder
        arm.move_angles(128, 90, -45),     # move arm up
    ])

def arm_put_tray_into_drum_area():
    return seq([
        arm.move_angles(-90, 90, -45),
        arm.move_angles(-90, 40, 0),
    ])

def return_tray_to_tray_holder_phase1():
    return seq([
        arm.move_angles(-90, 90, -100),   # go to 90-90 so the arm can lift the tray
        arm.move_angles(-90, 90, -40),    # lift the tray (hopefully)
    ])

def return_tray_to_tray_holder_phase2():
    return seq([
        arm.move_angles(115, 90, -50, speed=200),  # move over tray holder
        arm.move_angles(115, 90, -100, speed=200),  # place tray down
        arm.move_angles(140, 90, -100, speed=200),  # move it back so it sits fully on the tray holder

        arm.move_angles(110, 90, -100),
        arm.move_angles(110, 90, 0),
    ])



def arm_test_tray_positions():
    return seq([
        wait_for_button("go"),
        parallel(
            arm.move_angles(115, 82, -45),
            Defs.arm_claw.closed(),
        ),
        wait_for_button(),

        arm.move_angles(115, 96, -102),    # move down
        wait_for_button(),
        arm.move_angles(128, 96, -102),    # move to the side under holder
        wait_for_button(),
        arm.move_angles(128, 90, -45),     # move arm up

        wait_for_button("place down"),
        arm.move_angles(-90, 90, -45),
        wait_for_button(),
        arm.move_angles(-90, 40, 0),
        wait_for_button(),
        arm.move_angles(-90, 45, -80, speed=100),    # fully put tray on the floor

        wait_for_button("move forward, then: pickup"),
        arm.move_angles(-90, 50, -30),
        wait_for_button(),
        arm.move_angles(-90, 90, -100),   # go to 90-90 so the arm can lift the tray
        wait_for_button(),
        arm.move_angles(-90, 90, -50),    # lift the tray (hopefully)
        wait_for_button(),
        arm.move_angles(115, 90, -50, speed=100),  # move over tray holder
        wait_for_button(),
        arm.move_angles(115, 90, -100, speed=60),  # place tray down
        wait_for_button(),
        arm.move_angles(140, 90, -100, speed=70),  # move it back so it sits fully on the tray holder
        wait_for_button(),

        arm.move_angles(110, 90, -100),
        wait_for_button(),
        arm.move_angles(110, 90, 0),

        wait_for_button("disable"),
        fully_disable_servos(),
    ])