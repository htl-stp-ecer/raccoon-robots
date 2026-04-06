from libstp import *

from src.hardware.defs import Defs


class M080dropMachingPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #position over basket
            turn_right(10),
            strafe_right(cm=3),
            Defs.pom_arm.above_basket(130),
        ])