from libstp import *

from src.hardware.defs import Defs


class M100DropMachedPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #move over basket
            strafe_left().until(
                on_black(Defs.front.left) >
                on_white(Defs.front.left)
            ),
            turn_to_heading_right(10),

            #move arm down and open
            Defs.pom_arm.up(),
            Defs.pom_grab.slightly_open(75),

            shake_servo(Defs.pom_grab, 3, 60, 90),
            Defs.pom_grab.slightly_open(75),

            #compress down
            Defs.pom_arm.drop_poms_pos(),
            Defs.pom_grab.closed(),

            loop_for(
                seq([
                    Defs.pom_arm.down(50),
                    Defs.pom_arm.drop_poms_pos(100),
                ]),
                iterations=3
            ),

            drive_forward(cm=3),

            loop_for(
                seq([
                    Defs.pom_grab.wide_open(60),
                    Defs.pom_grab.pom_width(),
                ]),
                iterations=9
            ),

        ])