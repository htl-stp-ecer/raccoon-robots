from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_recover_from_over_limit, drum_lifting_down


class M1009TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            wait_for_button(),
            drum_recover_from_over_limit(Defs.lift_drums_servo.up),
            wait_for_button(),
            parallel(
                drive_forward(cm=27),
                Defs.drum_pusher_servo.open(),
                seq([
                    wait_until_distance(12),  # only a good guess of distance
                    drum_lifting_down(slow_mode=False),
                ]),
            ),
        ])
