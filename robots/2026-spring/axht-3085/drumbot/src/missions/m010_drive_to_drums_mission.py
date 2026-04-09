from libstp import *

from src.hardware.defs import *
from src.steps.drum_lifting_step import *
from src.steps.servo_steps import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),

        parallel(
                drum_lifting_up(),
                seq([
                    wait_for_seconds(0.4), #TODO: comfirm if we need the wait
                    push_orange_pom_away(),
                    turn_right(90),

                ]),
            ),


             parallel(
                 drive_forward(67),
                 seq([
                     wait_until_distance(14),
                     Pom_puher_Start(),
                 ]),
                 seq([
                     wait_until_distance(55),
                     drum_lifting_down(slow_mode=False),
                 ])
             )
        ])
