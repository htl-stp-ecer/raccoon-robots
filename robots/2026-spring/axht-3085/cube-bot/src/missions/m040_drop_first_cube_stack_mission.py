from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs


def _follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=1)
        .correct_lateral()
        .pid(kp=0.6, ki=0.5, kd=0.05)
    )


def align_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=0.4)
        .correct_lateral(hold_heading=False)
        .pid(kp=0.6, ki=0.3, kd=0.0)
    )


class M040DropFirstCubeStackMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            background(
                step=seq([
                    wait_for_background("arm_up"),
                    arm.move_angles( #move servo forward
                        0, 110, -60, speed=150
                    ),
                ])
            ),

            # drive to external loading dock while rotating arm
            strafe_left(heading=0).until(
                on_black(Defs.rear.left)
            ),
            _follow().until(
                after_cm(120)
            ),
            parallel(
                align_line_follow().until(
                    after_seconds(0.4),
                ),
                arm.move_angles(
                    base_deg=91, speed=80
                ),
            ),
            mark_heading_reference(),
            strafe_left(heading=0).until(
                on_black(Defs.rear.left)
            ),
            turn_to_heading_right(0),

            # place cube tower
            arm.move_angles(91,elbow_deg=-63, speed=150),
            arm.move_angles(sholder_deg=80, speed=200),
            wait_for_seconds(0.5),
            wait_for_button(),
            Defs.arm_claw.open(),
        ])
