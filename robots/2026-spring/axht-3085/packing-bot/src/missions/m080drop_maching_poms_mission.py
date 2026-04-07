from libstp import *

from src.hardware.defs import Defs


class M080dropMachingPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #close shild after we droped the poms
            background(
                seq([
                    wait_for_seconds(1),
                    Defs.shild_graber.closed(),
                ]),
            ),

            #position over basket
            turn_right(20),
            drive_angle(120, 17.5),

            #move the basket a bit forward
            drive_forward(cm=4),
            drive_backward(cm=5),
            Defs.pom_arm.above_basket(),
            wait_for_seconds(0.5),

            #shake servos out
            loop_for(
                seq([
                    Defs.pom_grab.shake_pos_a(250),
                    Defs.pom_grab.shake_pos_b(250)
                    ]),
                iterations=3,
            ),
            #shake_servo(Defs.pom_grab,
            #            duration=1,
            #            angle_a=Defs.pom_grab.shake_pos_a.value,
            #            angle_b=Defs.pom_grab.shake_pos_b.value,
            #            ),

            #compress poms
            Defs.pom_grab.closed(),
            Defs.pom_arm.in_basket(90),

            #drive closer
            Defs.pom_arm.high_above_basket(),
            drive_forward(cm=7),

            #drop poms a second time
            Defs.pom_grab.wide_open(),
            Defs.pom_arm.high_above_basket(),
            wait_for_seconds(0.5),

            loop_for(
               seq([
                   Defs.pom_grab.closed(),
                   wait_for_seconds(0.1),
                   parallel(
                       Defs.pom_grab.wide_open(),
                   ),
               ]),
                iterations=1
            ),

            #compress poms
            parallel(
                Defs.pom_grab.closed(),
                Defs.shild.grab_pasked(), #grab sorted poms
                drive_backward(cm=12),
            ),
            Defs.pom_arm.in_basket(90),





        ])