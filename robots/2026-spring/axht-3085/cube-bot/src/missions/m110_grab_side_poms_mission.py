from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm


class M110GrabSidePomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            arm.move_angles(elbow_deg=45)
            parallel(
                strafe_right().until(
                    on_black(Defs.front.right)
                ),
                arm.move_angles(base_deg=90, sholder_deg=10,elbow_deg=-10),
                Defs.arm_claw.grab(),


            )
        ])