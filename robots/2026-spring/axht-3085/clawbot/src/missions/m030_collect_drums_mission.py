from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import *


def line_follow():
    return strafe_follow_line_single(
        Defs.front.right,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.2,
        kd=0.0,
    )


def backward_line_follow():
    return strafe_follow_line_single(
        Defs.front.right,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.2,
        kd=0.0,
    )


class M030CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # Grab tray and position over drum area
            parallel(
                seq([
                    turn_to_heading_left(0),
                    strafe_left().until(
                        over_line(Defs.front.right)
                    ),
                    turn_to_heading_left(0),
                ]),
                seq([
                    wait_for_background("drop_cone"),
                    arm_grab_tray(),
                    arm_put_tray_into_drum_area(),
                ]),
            ),

            # Drive backwards
            line_follow().until(
                over_line(Defs.rear.left)
                + after_cm(15)
            ),

            # Wait and more arm stuff
            wait_for_checkpoint(70),
            turn_to_heading_left(0),
            arm.move_angles(-90, 45, -80, speed=100),    # fully put tray on the floor

            # Drive the length of the drum area while pushing tray through drum area
            backward_line_follow().until(
                over_line(Defs.rear.left)
                + over_line(Defs.front.left)
                + after_cm(8)
            ),

            # Correct heading, lift tray out of drum area and drive forward until black line
            turn_to_heading_left(0),
            parallel(
                drive_forward().until(
                    on_black(Defs.front.left)
                ),
                arm.move_angles(-90, 40, -30),    # slightly lift tray ahead of full sequence
            ),

            # return tray to tray holder
            return_tray_to_tray_holder_phase1(),
            background(
                step=return_tray_to_tray_holder_phase2(),
                name="return_tray"
            ),
        ])
