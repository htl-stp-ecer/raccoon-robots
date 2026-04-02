from libstp import *

from src.hardware.defs import Defs
from src.steps.et_scan_align import EtScanAlign


class M100DropMachedPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #move over basket
            strafe_left().until(
                on_black(Defs.front.left) >
                #on_white(Defs.front.left) >
                after_cm(5)
            ),
            turn_to_heading_right(0),
            EtScanAlign(
               60,
                "right",
                1.0,
                0,
                Defs.distance_sensor
            ),
            Defs.pom_arm.above_basket(),
            turn_right().until(after_degrees(30) | after_seconds(0.5)),
            turn_to_heading_right(0),

            #move arm down and open
            Defs.pom_arm.up(),
            Defs.pom_grab.slightly_open(100),

            shake_servo(Defs.pom_grab, 1.5, 60, 90),
            Defs.pom_grab.slightly_open(100),

            #compress down
            Defs.pom_arm.drop_poms_pos(),
            Defs.pom_grab.closed(),

            loop_for(
                seq([
                    Defs.pom_arm.down(50),
                    Defs.pom_arm.drop_poms_pos(100),
                ]),
                iterations=1
            ),

            drive_forward(cm=5),

            loop_for(
                seq([
                    Defs.pom_grab.closed(),
                    Defs.pom_grab.wide_open(),
                    wait_for_seconds(1.0),
                ]),
                iterations=2
            ),

        ])