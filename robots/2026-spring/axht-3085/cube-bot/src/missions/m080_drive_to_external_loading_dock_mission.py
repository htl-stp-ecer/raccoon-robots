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
                # fallback if we miss the black line on the bottom, so we still try to finish the run
                # (wont help if we are stuck on the upper loading dock
                fallback=seq([
                    drive_backward().until(
                        on_black(Defs.rear.left)
                    ),
                    drive_forward(cm=10),
                ])
            ),

            # .on_anomaly(
            #    callback_or_step=seq([
            #        strafe_right().until(  # try to move pallet out of the way, if we stuck on it
            #            on_black(Defs.rear.left) | after_seconds(1)
            #        ),
            #        drive_backward(cm=10),  # get free
            #        # move back in position to drive down the ram
            #        strafe_left().until(
            #            on_black(Defs.front.left)
            #            + after_cm(10),
            #        ),
            #        # magic deg so we hit the right eghe of
            #        drive_forward(cm=40, heading=0),  # go on ramp befor starting to linfollow again

            #        _follow().until(
            #            after_cm(10)
            #            + over_line(Defs.rear.left)
            #            + after_cm(5)
            #        )
            #    ])
            # ),

            switch_calibration_set("default"),
            strafe_right(heading=0).until(
                over_line(Defs.front.right)
                + over_line(Defs.front.right)
                + over_line(Defs.rear.left)
            ),
            strafe_right(cm=10, speed=0.5),

            # align on wall
            wall_align().until(
                after_seconds(2.5),
            ),
        ])
