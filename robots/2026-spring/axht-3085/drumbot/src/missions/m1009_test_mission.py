from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lineup_step import lineup_drum_with_pipe
from src.steps.drum_lifting_step import drum_recover_from_over_limit
from src.steps.range_finder import turn_to_peak


class M1009TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
            loop_for(
                seq([
                    wait_for_button("Drive to pos"),
                    drive_forward(speed=0.7).until(
                        over_line(Defs.front_right_ir_sensor) +
                        after_cm(23)
                    ),
                    wait_for_button("Do a turn to peak"),
                    turn_to_peak(
                        turn_speed=0.3,
                        sweep_deg=40,
                    ),
                    wait_for_button("To Analog"),
                    drive_to_analog_target(Defs.et_range_finder, 0.2),
                ]),
                10
            ),
        ])
