from libstp import *

from src.hardware.defs import Defs


class M080dropMachingPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #close shild after we droped the poms
            background(
                seq([
                    wait_for_seconds(1),
                    Defs.pom_grab.closed(),
                ]),
            ),

            #position over basket
            turn_right(20),
            drive_angle(120, 15),

            #move the basket a bit forward
            drive_forward(cm=4),
            drive_backward().until(after_cm(7)),
            Defs.pom_arm.above_basket(),

            #shake servos out
            Defs.pom_grab.shake_pos_b(100),
            shake_servo(Defs.pom_grab,
                        duration=1,
                        angle_a=Defs.pom_grab.shake_pos_a.value,
                        angle_b=Defs.pom_grab.shake_pos_b.value,
                        ),

            #compress poms
            Defs.pom_grab.closed(),
            Defs.pom_arm.in_basket(),

            #drive closer
            Defs.pom_arm.high_above_basket(),
            drive_forward(cm=8),

            #drop poms a second time
            Defs.pom_grab.wide_open(),
            wait_for_seconds(0.5),

            loop_for(
               seq([
                   Defs.pom_grab.closed(),
                   wait_for_seconds(0.1),
                   parallel(
                       Defs.pom_grab.wide_open(),
                       Defs.pom_arm.high_above_basket(),
                   ),
               ]),
                iterations=3
            ),

            #compress poms
            Defs.pom_grab.closed(),
            Defs.pom_arm.in_basket(),

        ])