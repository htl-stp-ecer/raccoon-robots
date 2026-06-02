from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm


class M060GrabGreenCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            strafe_right().until(
                over_line(Defs.front.right)
            ),

            arm.move_angles(-90, 40, -20),
            arm.move_angles(-90, 45, -15),
        ])