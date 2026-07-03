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
        .move(strafe=-0.3)
        .correct_forward(hold_heading=False)
        .pid(kp=0.4, ki=0.1, kd=0.0)
    )


def weird_cube_drive():
    approach = drive_until_impact(max_cm=50, speed=1, accel_threshold=0.4)  # bis 50cm ODER Aufprall

    def drive_backward_if_cube(robot):
        robot.debug(f"drive_backward_if_cube: approach impact result: {approach.impact_result.forward_cm}")
        if approach.impact_result.forward_cm >= 45:
            return drive_backward(heading=0).until(
                after_cm(28)
            )
        else:
            return drive_backward(heading=0).until(
                after_cm(16)
            )

    return seq([
        approach,
        strafe_right(cm=5, speed=0.5, heading=0),  # make sure we are accectly on the pipe

        # move away from wall to avoid hitting already present cube stack
        drive_backward(heading=0).until(
            after_cm(28)
        ),
        defer(lambda robot: drive_backward_if_cube),
    ])



class M080DriveToExternalLoadingDockMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            timeout_or(
                step=_follow().until(
                    over_line(Defs.rear.left)
                    + after_cm(90)
                    + over_line(Defs.rear.left)
                ),
                seconds=9,
                # fallback if we miss the black line on the bottom, so we still try to finish the run
                # (won't help if we are stuck on the upper loading dock)
                fallback=optimize([
                    drive_backward(heading=0).until(
                        on_black(Defs.rear.left)
                    ),
                    strafe_left(cm=30, heading=0)
                ])
            ),

            switch_calibration_set("default"),

            optimize([
                turn_to_heading_left(90),

                wall_align_forward( #
                    speed=0.3,
                    accel_threshold=10,
                    settle_duration=0,
                    max_duration=1,
                    grace_period=1
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
                turn_to_heading_left(0),
                strafe_right(cm=20, speed=0.5, heading=0),

                # align on wall
                weird_cube_drive(),
            ]).cut_corners(5, cut_until=True),
        ])
