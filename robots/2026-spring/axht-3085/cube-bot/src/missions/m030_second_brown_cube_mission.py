from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import *


def _follow():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=-1)
        .correct_lateral(hold_heading=True)
        .hold_heading(0)
        .pid(kp=0.4, ki=0.03, kd=0.0)
    )


class M030SecondBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                # start moving arm by 90° as soon as black line was crossed
                seq([
                    wait_for_background(name="drop_cube"),
                    arm.move_angles(0, 65, 0, speed=150),
                    Defs.arm_claw.idle(),
                    grab_left_brown_cube_start_pos()
                ]),

                # drive backwards to 2nd cube pickup
                timeout_or(
                    step=seq([
                        _follow().until(
                            over_line(Defs.front.right)
                            + after_cm(17)
                        ),
                    ]),
                    seconds=5,
                    fallback=seq([
                        timeout_or(
                            step=drive_forward().until(
                                on_black(Defs.front.right)
                            ),
                            seconds=6,
                            fallback=seq([]),
                        ),
                        timeout_or(
                            step=_follow().until(
                                (over_line(Defs.front.right)
                                 + after_cm(17))
                            ),
                            seconds=6,
                            fallback=seq([]),
                        ),
                    ]),
                ),
            ),
            # go into correct lateral position for pickup
            timeout_or(
                step=strafe_right(heading=0, speed=0.5).until(
                    on_black(Defs.rear.left),
                ),
                seconds=2,
                fallback=seq([  # if we are stuck on the cone, try to drive forward so we get the conde out
                    drive_backward(cm=5),
                    drive_forward(cm=5),
                    timeout(
                        step=strafe_right(heading=0, speed=0.5).until(
                            on_black(Defs.rear.left),
                        ),
                        seconds=2,
                    )
                ])
            ),

            grab_brown_cube(LineSide.RIGHT, heading=0),
            turn_to_heading_right(0),
        ])
