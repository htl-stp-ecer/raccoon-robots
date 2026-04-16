from raccoon import *

from src.steps.drum_lifting_step import drum_lifting_down


class M1009TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drum_lifting_down(slow_mode=False),
            # fully_disable_servos(),
            # wait_for_button(),
            # drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
            # seq([
            #     wait_for_button("PIPE"),
            #     lineup_drum_with_pipe()
            # ]),
        ])
