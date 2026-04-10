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
            drive_angle(120, 19),

            #move the basket a bit forward
            drive_forward(cm=5),
            parallel(
                drive_backward(cm=8),
                Defs.pom_arm.above_basket(150),
            ),
            wait_for_seconds(0.5),

            #shake servos out
            Defs.pom_grab.shake_pos_a(100),
            wait_for_seconds(0.2),
            Defs.pom_grab.closed(),
            loop_for(
                step=seq([
                    Defs.pom_grab.shake_pos_a(),
                    Defs.pom_grab.shake_pos_b()
                    ]),
                iterations=2,
            ),

            #compress poms
            Defs.pom_grab.closed(),
            Defs.pom_arm.in_basket(90),

            #drive closer
            Defs.pom_arm.high_above_basket(),
            drive_forward(cm=7),

            #drop poms a second time
            Defs.pom_grab.wide_open(150),
            Defs.pom_arm.high_above_basket(),
            wait_for_seconds(0.5),

            #compress poms
            Defs.pom_grab.closed(),
            wall_align_backward(1.0, 0.6, 0.0, 0.6, 0.3),
            Defs.pom_arm.in_basket(90),

            #pull claw up again
            Defs.pom_arm.high_above_basket(),
            drive_forward(cm=7),
            #drop poms a third time
            Defs.pom_grab.wide_open(),
            wait_for_seconds(0.1),

            #compress poms
            parallel(
                Defs.pom_grab.closed(),
                Defs.shild.grab_pasked(), #grab sorted poms
                wall_align_backward(1.0, 0.6, 0.0, 0.7, 0.3),
            ),
            mark_heading_reference(origin_offset_deg=90),
            Defs.pom_arm.in_basket(90),





        ])