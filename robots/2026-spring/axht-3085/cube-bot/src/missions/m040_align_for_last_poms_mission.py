from libstp import *

from src.hardware.defs import Defs


class M040AlignForLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(26, 1.0),
            #push a blue pom to collect it later
            background(
                seq([
                    wait_for_seconds(0.4),
                    Defs.pom_arm.high_up(100),
                ]),
                name="put claw up"
            ),

            turn_to_heading_right(90),

            parallel(
                seq([
                    strafe_right().until(on_black(Defs.rear.right)), #TODO: make use a timout if we don't find the black line
                    strafe_left(13, 1.0), #magic hardcoded value :)
                ]),

                #prepare the shield to grab the sorted poms
                Defs.shild.down(),
                Defs.shild_graber.wide_open(),
            ),
            turn_to_heading_right(90, 1.0),

            drive_backward(25, 1.0),

            parallel(
                wall_align_backward(1.0, 0.4, 0.0, 3.0),
                Defs.shild_graber.closed(70),
            ),
            # mark heading for collecting the poms (0 heading is now in the direction of the black line)
            mark_heading_reference(),

            #grab the pom set
            drive_forward(cm=5, speed=0.6),
            Defs.shild.save_up(),
        ])
