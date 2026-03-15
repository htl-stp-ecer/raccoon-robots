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
            Defs.pom_arm.down(),
            wait_for_seconds(0.5),
            wall_align_backward(1.0, 0.4, 0.0, 2),
            Defs.pom_grab.wide_open(),
            wait_for_seconds(1),

            #collect poms
            drive_forward(11, 1.0),
            drive_backward(1.0, 1.0),
            Defs.pom_grab.pom_width(100),
            Defs.pom_grab.magic_val_for_m06(100),
            parallel(
                drive_forward(45, 1.0),
                seq([
                    wait_until_distance(5),
                    Defs.pom_grab.wide_open(),
                ]),
            ),

            Defs.pom_grab.closed(),
            wait_for_seconds(0.3),
            Defs.pom_arm.high_up(),
        ])
