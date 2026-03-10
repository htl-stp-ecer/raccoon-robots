from libstp import *
from src.hardware.defs import Defs


class M05AlignForLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(18, 1.0),
            #push a blue pom to collect it later
            parallel(
                turn_right(90, speed=1.0),
                seq([
                    wait_for_seconds(0.55),
                    Defs.pom_arm.high_up(),
                ]),
            ),

            parallel(

                seq([
                    strafe_right(1.0).until(on_black(Defs.rear_right_light_sensor)),
                    strafe_left(17, 1.0), #magic hardcoded value :)
                ]),

                #prepare the shield to grab the sorted poms
                Defs.shild.down(),
                Defs.shild_graber.open(),
            ),
            turn_to_heading(-90, 1.0),

            drive_backward(25, 1.0),
            #grab the pom set

            Defs.shild_graber.closed(),
            Defs.shild.up(),

            #wall_align_backward(1.0, 0.3, 0.1, 1.0),
            #mark_heading_reference(),  # mark heading for collecting the poms
        ])
