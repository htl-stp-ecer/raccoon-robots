from libstp import *

from src.hardware.defs import Defs


class M08DropSortedPomsAndReturnThemMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            strafe_left().until(on_black(Defs.rear.right)),
            Servo.pom_arm.start(),
            Defs.shild.down(),

            drive_backward(cm=10),

            strafe_right().until(
                on_black(Defs.front.left) >
                after_cm(8)
            ),
        ])