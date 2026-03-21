from libstp import *
from src.hardware.defs import Defs


class M03GrabSecondPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #align on poms and put the claw down
            Defs.pom_arm.above_pom(300),
            wait_for_seconds(1),

            parallel(
                Defs.pom_grab.slightly_open(),
                Defs.pom_arm.down(300),
            ),
            Defs.pom_grab.open(),

            #push the oragne pom on the left to the side
            turn_left(15),
            turn_right(45),
            turn_to_heading(-10),


            parallel(
                drive_forward().until(on_black(Defs.front.left)),
                Defs.pom_grab.closed(),
            ),

        ])
