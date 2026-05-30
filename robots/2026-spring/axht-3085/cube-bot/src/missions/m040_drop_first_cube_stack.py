from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs

def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.right,
        speed=-1,
        side=LineSide.LEFT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )


class  M040DropFirstCubeStack(Mission):
    def sequence(self) -> Sequential:
        return seq([
            backward_line_follow().until(
                after_cm(110)
            ),
            turn_to_heading_left(180),
            drive_backward(heading=0).until(
                after_cm(5)
            ),
        ])