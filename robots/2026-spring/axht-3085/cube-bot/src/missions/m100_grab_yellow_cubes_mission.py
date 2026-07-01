from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm


class M100GrabYellowCubesMission(Mission):
    def sequence(self) -> Sequential:
        return optimize([
            arm.move_angles(-90, 40, -40),
            strafe_left().until(
                over_line(Defs.front.right)
            ),
            Defs.arm_claw.strong_grab(),
            arm.move_angles(-90, 90, -40),
            drive_backward(cm=16),
            arm.move_angles(elbow_deg=-92),
            Defs.arm_claw.open(),
        ]).cut_corners(5)