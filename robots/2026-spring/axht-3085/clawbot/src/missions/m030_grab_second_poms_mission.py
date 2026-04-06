from libstp import *
from src.hardware.defs import Defs


class M030GrabSecondPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([

            parallel(
                Defs.pom_grab.open(100),
                Defs.pom_arm.down(200),
            ),
            wait_for_seconds(0.5),

            #push the oragne pom on the left to the side
            turn_left(10).speed(0.3),
            turn_right(35),
            turn_to_heading_right(15),
            strafe_left(cm=5),


            parallel(
                Defs.pom_grab.closed(),
                drive_forward().until(
                    on_black(Defs.front.left) +
                    after_cm(26),
                ),
            ),
        ])
