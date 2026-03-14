from libstp import *
from src.hardware.defs import Defs


class M06CollectLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(1.0, 1.0),
            strafe_left(speed=0.5).until(on_white(Defs.front.left, threshold=0.3)),
            drive_backward(1.0, 1.0),

            strafe_right(speed=1.0, cm=6),

            #align for poms
            turn_to_heading(-90, 1.0),
            Defs.pom_arm.down(),  # put down claw so we can strafe easier
            wait_for_seconds(0.5),
            wall_align_backward(1.0, 0.4, 0.0, 2),
            Defs.pom_grab.wide_open(),
            wait_for_seconds(1),

            #collect poms
            parallel(
                drive_forward(50, 1.0),
                seq([
                    Defs.pom_grab.pom_width(200), #not the normal slightliy open (zahnradspiel ist real)
                    wait_until_distance(15),
                    Defs.pom_grab.wide_open(),
                ]),
            ),

            Defs.pom_grab.closed(),
            Defs.pom_arm.high_up(),
        ])
