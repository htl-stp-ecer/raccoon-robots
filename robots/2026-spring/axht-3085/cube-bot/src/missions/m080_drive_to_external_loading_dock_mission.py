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
        .hold_heading(0)
        .pid(kp=0.8, ki=0.3, kd=0.01)
    )

def weird_cube_drive():
    approach = DriveUntilImpact(max_cm=50, speed=1,
                                accel_threshold=10)  # ← Klasse, nicht Factory!

    def drive_backward_if_cube(robot):
        robot.info(f"drive_backward_if_cube: approach impact result: {approach.impact_result}")
        if approach.impact_result.forward_cm >= 45:
            return drive_backward(heading=0).until(
                after_cm(28)
            )
        else:
            robot.error(f"cube in the way")
            return drive_backward(heading=0).until(
                after_cm(28)
            )

    return seq([
        approach,
        strafe_right(cm=5, speed=0.5, heading=0),  # make sure we are accectly on the pipe

        # move away from wall to avoid hitting already present cube stack
        defer(drive_backward_if_cube),
    ])


class M080DriveToExternalLoadingDockMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            timeout_or(
                step=_follow().until(
                    after_cm(110)
                    + (over_line(Defs.rear.left) | on_level(2))
                    + after_cm(1)
                ),
                seconds=8,
                # fallback if we miss the black line on the bottom, so we still try to finish the run
                # (won't help if we are stuck on the upper loading dock)
                fallback=optimize([
                    timeout_or(
                        step=drive_backward(heading=0).until(
                            on_black(Defs.rear.left)
                        ),
                        seconds=2,
                        fallback=seq([
                            timeout_or(
                                step=_follow().until(
                                    after_cm(90)
                                    + over_line(Defs.rear.left)
                                ),
                                seconds=4,
                                # fallback if we miss the black line on the bottom, so we still try to finish the run
                                # (won't help if we are stuck on the upper loading dock)
                                fallback=optimize([
                                    timeout(
                                        step=drive_backward(heading=0).until(
                                            on_black(Defs.rear.left)
                                        ),
                                        seconds=1,
                                    )
                                ]),
                            ),
                        ]),
                    ),
                    strafe_left(cm=20, heading=0)
                ])
            ),
            drive_backward().until(on_black(Defs.rear.left)),

            switch_calibration_set("default"),

            # optimize([ #TODO: enable teh optimize

            # make sure we have no game peaces in front of the pipe
            drive_forward(cm=5, heading=5),
            drive_backward(cm=5, heading=0),

            turn_to_heading_left(90),

            wall_align_forward(  #
                speed=0.3,
                accel_threshold=10,
                settle_duration=0,
                max_duration=0.9,
                grace_period=0.9
            ),
            mark_heading_reference(origin_offset_deg=-90),

            timeout(
                step=seq([
                    drive_backward(heading=90).until(
                        on_black(Defs.front.right)
                        + after_cm(25)
                        + on_black(Defs.front.right)
                    ),
                ]),
                seconds=7
            ),

            # ]).cut_corners(5, cut_until=True),
        ])
