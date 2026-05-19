from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm


def line_follow():
    return strafe_follow_line_single(
        Defs.front_left_light_sensor,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.3,
        kd=0.0,
    )


class M010DriveDownRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("upper"),
            mark_heading_reference(),

            # drive to black line
            turn_left(25),
            drive_backward().until(
                over_line(Defs.rear.left)
                + on_black(Defs.rear.left)
            ),
            turn_to_heading_right(0),

            # move arm to shift center of gravity for balance and better grip
            background(
                arm.move_angles(0, 0, 10),
            ),

            # revert arm position and turn to absolute heading
            background(
                seq([
                    wait_for(
                        after_cm(110)
                        + over_line(Defs.rear.left)
                    ),
                    arm.move_angles(-12, 90, 0),
                ])
            ),

            # make sure we are centered on black line
            line_follow().until(
                after_cm(110)
                + over_line(Defs.front.right)
            ),

            turn_to_heading_right(0),
            switch_calibration_set("default"),
        ])
