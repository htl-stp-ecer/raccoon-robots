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
                seq([ #wait shortly so the poms don't drop out
                    wait_for_seconds(0.1),
                    Defs.shild_graber.open(),
                ])
            ),
        ])