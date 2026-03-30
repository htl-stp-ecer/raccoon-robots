from libstp import *
from src.hardware.defs import Defs


class M030GrabSecondPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #align on poms and put the claw down
            Defs.pom_arm.above_pom(100),

            parallel(
                Defs.pom_grab.open(100),
                Defs.pom_arm.down(200),
            ),
            wait_for_seconds(0.5),

            #push the oragne pom on the left to the side
            turn_left(10).speed(0.4),
            turn_right(35),
            turn_to_heading_right(15),
            strafe_left(cm=5),


            parallel(
                drive_forward().until(on_black(Defs.front.left)),
                Defs.pom_grab.closed(),
            ),

        ])
