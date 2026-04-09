from libstp import *

from src.hardware.defs import Defs


class M070PullBasketsOutMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #drive to baskets and grab
            Defs.shild._45deg(),
            strafe_right(cm=7),
            Defs.shild.grab_pasked(),

            strafe_left().until(on_black(Defs.rear.right)),
            turn_right(70, speed=0.5),
            #drop sorted poms
            parallel(
                Defs.shild.above_pasked(),
                Defs.shild_graber.open(),
            ),
        ])