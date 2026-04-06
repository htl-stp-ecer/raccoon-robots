from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_lifting_up, drum_lifting_down


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),
            parallel(
                drum_lifting_up(),
                 seq([
                     wait_for_seconds(0.4),
                     turn_right(90),
                 ]),
             ),
             parallel(
                 drive_forward(67),
                 seq([
                     wait_until_distance(16),
                     Defs.pom_remover_servo.push_first_orange_pom_away(),
                     Defs.pom_remover_servo.start(),
                 ]),
                 seq([
                     wait_until_distance(55),
                     drum_lifting_down(slow_mode=False),
                 ])
             ),
        ])
