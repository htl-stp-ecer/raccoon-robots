from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_lifting_up, drum_lifting_down


class M01DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),
            Defs.pom_remover_servo.push_first_orange_pom_away(),
            parallel(
                drum_lifting_up(),
                 seq([
                     wait_for_seconds(0.4),
                     turn_right(90),
                 ]),
             ),
             parallel(
                 drive_forward(65),
                 seq([
                     wait_until_distance(15),
                     Defs.pom_remover_servo.standby(),
                 ]),
                 seq([
                     wait_until_distance(55),
                     drum_lifting_down(slow_mode=False),
                 ])
             ),
        ])
