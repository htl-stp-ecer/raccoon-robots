from libstp import *

from src.hardware.defs import Defs


class M070PullBasketsOutMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            Defs.shild.above_pasked(),
            strafe_right(cm=2),
            Defs.shild.grab_pasked(),

            strafe_left().until(on_black(Defs.rear.right)),
            turn_right(120),
            #drop sorted poms
            parallel(
                Defs.shild.above_pasked(),
                Defs.shild_graber.open(),
            ),
        ])