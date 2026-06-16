from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.calibrate_analog_drive import on_analog_flank
from src.steps.line_follow_builder import line_follow


def _follow():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(heading=1)
        .correct_lateral()
        .pid(kp=0.5, ki=0.3, kd=0.0)
    )


def wall_align():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.RIGHT)
        .move(heading=1)
        .correct_lateral(hold_heading=False)
        .pid(kp=0.6, ki=0.6, kd=0.05)
    )


class M080DriveToExternalLoadingDockMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            timeout_or(
                step=_follow().until(
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
