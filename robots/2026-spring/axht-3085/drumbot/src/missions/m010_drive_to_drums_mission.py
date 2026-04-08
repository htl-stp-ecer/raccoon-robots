from libstp import *

from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),

            parallel(
                drum_lifting_up(),
                seq([
                    #wait_for_seconds(0.4), #TODO: comfirm if we need the wait
                    turn_right(90),
                ]),
                seq([
                    wait_until_degrees(15),
                    Defs.pom_remover_servo.push_blue_pom_away(),
                ]),
            ),


             parallel(
                 drive_forward(67),
                 seq([
                     Defs.pom_remover_servo.start(),
                     wait_until_distance(10),
                     Defs.pom_remover_servo.push_blue_pom_away(),
                     Defs.pom_remover_servo.start(),
                 ]),
                 seq([
                     wait_until_distance(55),
                     drum_lifting_down(slow_mode=False),
                 ])
             )
        ])
