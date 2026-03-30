from libstp import *

from src.hardware.defs import Defs


class M070DropSortedPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # grab the one basket
            Defs.shild.above_pasked(),
            strafe_right(cm=1),
            Defs.shild.grab_pasked(),

            # pull the basktet out
            strafe_left().until(
                on_black(Defs.front.right) >
                on_white(Defs.front.right)
        ),
            Defs.shild.above_pasked(),
            strafe_left(cm=5),

            #align ouselfs to drop
            drive_forward().until(
                on_black(Defs.rear.right) >
                on_white(Defs.rear.right)
            ),

            #drop poms
            strafe_right(speed=0.6).until(
                on_black(Defs.front.left)
            ),
            Defs.shild_graber.open(),

            #drive back and close claw
            strafe_left().until(
                on_white(Defs.front.left)
            ),
            parallel(
                Defs.shild_graber.closed(),
                Defs.shild.save_up(),
            ),
        ])