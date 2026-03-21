from libstp import *
from src.hardware.defs import Defs


class M05AlignForLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(25, 1.0),
            #push a blue pom to collect it later
            parallel(
                turn_to_heading(-90),
                seq([
                    wait_for_seconds(0.4),
                    Defs.pom_arm.high_up(100),
                ]),
            ),

            parallel(

                seq([
                    strafe_right(1.0).until(on_black(Defs.rear.right)),
                    strafe_left(13, 1.0), #magic hardcoded value :)
                ]),

                #prepare the shield to grab the sorted poms
                Defs.shild.down(),
                Defs.shild_graber.open(),
            ),
            turn_to_heading(-90, 1.0),

            drive_backward(25, 1.0),
            wall_align_backward(1.0, 0.4, 0.0, 3.0),
            #grab the pom set

            Defs.shild_graber.closed(70),
            Defs.shild.up(),
            mark_heading_reference(),  # mark heading for collecting the poms
        ])
