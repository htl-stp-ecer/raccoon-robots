from libstp import *
from src.hardware.defs import Defs


class M06CollectLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(5.0, 1.0),
            strafe_left(speed=0.5).until(on_white(Defs.front.left, threshold=0.3)),

            strafe_right(speed=1.0, cm=6),

            #align for poms
            turn_to_heading(-90, 1.0),
            Defs.pom_arm.down(),  # put down claw so we can strafe easier
            wall_align_backward(1.0, 0.3, 0.3, 3),
            Defs.pom_grab.wide_open(),
            wait_for_seconds(1),

            #collect poms
            parallel(
                drive_forward(50, 1.0),
                seq([
                    wait_until_distance(5),
                    Defs.pom_grab.slightly_open(), #not the normal slightliy open (zahnradspiel ist real)
                    wait_until_distance(20),
                    Defs.pom_grab.wide_open(),
                ]),
            ),

            Defs.pom_grab.closed(),
            Defs.pom_arm.high_up(),
        ])
