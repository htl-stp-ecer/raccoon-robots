from libstp import *
from src.hardware.defs import Defs


class M04GrabSecondPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #align on poms and put the claw down
            Defs.pom_arm.above_pom(300),
            wait_for_seconds(1),
            parallel(
                Defs.pom_arm.down(300),
                Defs.pom_grab.open(),
            ),

            #push the oragne pom on the left to the side
            turn_left(15),
            turn_right(40),
            turn_to_heading(0),

            parallel(
                Defs.pom_grab.pom_width(),
                Defs.front.drive_until_black(),
            ),

            Defs.pom_grab.closed(),
        ])
