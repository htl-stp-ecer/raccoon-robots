from raccoon import *

from src.hardware.defs import Defs


def left_lateral_align_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(strafe=-0.6)
        .correct_forward(hold_heading=False)
        .pid(kp=0.4, ki=0.1, kd=0.0)
    )


class M100TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_backward().until(
                on_black(Defs.rear.left)
            ),
            left_lateral_align_line_follow().until(
                after_seconds(4)
            )

        ])