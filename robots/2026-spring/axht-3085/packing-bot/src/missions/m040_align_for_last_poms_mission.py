from libstp import *

from src.hardware.defs import Defs


class M040AlignForLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #push a blue pom to collect it later
            background(
                seq([
                    wait_for_seconds(0.4),
                    Defs.pom_arm.start(100),
                ]),
                name="put claw up"
            ),
            # TODO: make sure we are on black
            #in the line strafe_right().until(on_black(Defs.rear.right)), we expect that we are on the black line or on the right of the black line
            #it should be deteckteed that we are on the left side of the black line and acount it.
            #The solution woud be that we track the Defs.rear.right ir sensor while we do the turn_to_heading_right(90),
            #the code shoud start when we reach 45deg and track which sensor reading we have.
            #if we only detected if we saw white then black (and white again; not not necessary)
            #we can do the strafe_right().until(on_black(Defs.rear.right)),
            #if we only saw white we should do strafe_left().until(over_line(Defs.rear.right)
            #in any cas we want to do the strafe left(13,1.0) afterwords


            turn_to_heading_right(90),


            parallel(
                seq([
                    strafe_right().until(on_black(Defs.rear.right)),
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
