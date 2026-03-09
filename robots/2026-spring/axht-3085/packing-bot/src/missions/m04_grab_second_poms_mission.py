from libstp import *
from src.hardware.defs import Defs
from src.steps.sensors import front


class M04GrabSecondPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #align on poms and put the claw down
            Defs.pom_arm.above_pom(),

            parallel(
                Defs.pom_arm.down(),
                Defs.pom_grab.open(speed=999),
            ),

            parallel(
                Defs.pom_grab.pom_width(),
                front.lineup_on_black(),
            ),

            Defs.pom_grab.closed(speed=999),
        ])
