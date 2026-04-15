from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_recover_from_over_limit, drum_eject_position, drum_seek
from src.steps.range_finder import turn_to_peak


class M1009TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            fully_disable_servos(),
            wait_for_button(),
            drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
            loop_for(
                seq([
                    wait_for_button("Turn to peak"),
                    drum_seek(),
                    wait_for_seconds(1),
                    turn_to_peak(
                        turn_speed=0.6,
                        sweep_deg=40,
                    ),
                ]),
                10
            ),
        ])
