from libstp import *

from src.hardware.defs import Defs
from src.steps.et_scan_align import EtScanAlign


class M100DropMachedPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #move over basket
            strafe_left().until(
                on_black(Defs.front.right) >
                on_white(Defs.front.right) >
                after_cm(5),
            ),
            turn_to_heading_right(0),
            wait_for_button(),
            EtScanAlign(
               50,
                "right",
                0.7,
                0,
                Defs.distance_sensor
            ),
            wait_for_button(),

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