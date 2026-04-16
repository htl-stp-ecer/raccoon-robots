from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_recover_from_over_limit, drum_eject_position, drum_seek
from src.steps.range_finder import turn_to_peak
from src.steps.drum_lineup_step import lineup_drum_with_pipe


class M1009TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),
            wait_for_button(),
            loop_forever(seq([
                turn_to_heading_left(0),
                wait_for_button(),
            ]))
            # fully_disable_servos(),
            # wait_for_button(),
            # drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
            # seq([
            #     wait_for_button("PIPE"),
            #     lineup_drum_with_pipe()
            # ]),
        ])
