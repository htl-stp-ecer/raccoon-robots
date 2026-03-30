from libstp import *

from src.hardware.defs import Defs



class M090ReturnSortedPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            strafe_left().until(on_black(Defs.rear.right)),
            Defs.pom_arm.start(),

            drive_backward(cm=10),

            strafe_right().until(
                on_black(Defs.front.left)
            ),
            strafe_left(cm=20),

            Defs.shild.down(),
            strafe_right(cm=35),
        ])