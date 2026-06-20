from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.calibrate_analog_drive import on_analog_flank


def _follow():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=1)
        .correct_lateral()
        .pid(kp=0.5, ki=0.3, kd=0.0)
    )


def wall_align():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.RIGHT)
        .move(forward=1)
        .correct_lateral(hold_heading=False)
        .pid(kp=0.6, ki=0.6, kd=0.05)
    )


def left_lateral_align_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(strafe=-0.6)
        .correct_forward(hold_heading=False)
        .pid(kp=0.4, ki=0.1, kd=0.0)
    )


class M080DriveToExternalLoadingDockMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            timeout_or(
                step=_follow().until(
                    over_line(Defs.rear.left)
                    + after_cm(140)
                    + over_line(Defs.rear.left)
                ),
                seconds=11,
                # fallback if we miss the black line on the bottom, so we still try to finish the run
                # (wont help if we are stuck on the upper loading dock
                fallback=seq([
                    drive_backward().until(
                        on_black(Defs.rear.left)
                    ),
                    drive_forward(cm=10),
                ])
            ),

            #wall_align_strafe_left(speed=0.2,
            #                       accel_threshold=10,
            #                       settle_duration=0,
            #                       max_duration=4, #make sure we have a stupid wall align without accel reading
            #                       grace_period=4
            #                       ),
            left_lateral_align_line_follow().until(
                after_seconds(4),
            ),
            mark_heading_reference(), #magic 2 deg, so the heading is correctt, bot is a bit shief wegen metal peace
            drive_forward(cm=5),

            switch_calibration_set("default"),
            strafe_right(heading=0).until(
                over_line(Defs.front.right)
                + over_line(Defs.front.right)
                + over_line(Defs.rear.left)
            ),
            strafe_right(cm=10, speed=0.5, heading=0),

            # align on wall
            wall_align().until(
                after_seconds(2.5),
            ),
            strafe_right(cm=15, speed=0.5, heading=0), #make sure we are accectly on the pipe
        ])
