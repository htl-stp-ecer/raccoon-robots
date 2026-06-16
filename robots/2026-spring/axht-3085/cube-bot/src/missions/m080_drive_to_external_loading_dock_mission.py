from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.calibrate_analog_drive import on_analog_flank
from src.steps.line_follow_dsl import lateral_follow_line_single, lateral_follow_line_single_free, \
    strafe_follow_line_single_free, strafe_follow_line_single


def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.5,
        ki=0.3,
        kd=0.0,
    )


def wall_align():
    return strafe_follow_line_single_free(
        sensor=Defs.rear.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.6,
        kd=0.05,
    )


class M080DriveToExternalLoadingDockMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            timeout_or(
                step=line_follow().until(
                    over_line(Defs.rear.left)
                    + after_cm(140)
                    + over_line(Defs.rear.left)
                    + after_cm(5)
                ),
                seconds=11,
                fallback=seq([
                    drive_backward().until(
                        on_black(Defs.rear.left)
                    ),
                    drive_forward(cm=10),
                ])
            ),

            switch_calibration_set("default"),
            strafe_right(heading=0).until(
                over_line(Defs.front.right)
                + over_line(Defs.front.right)
                + over_line(Defs.rear.left)
            ),

            # align on wall
            wall_align().until(
                after_seconds(2.0),
            ),
        ])
