from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lineup_step import lineup_drum_with_pipe
from src.steps.drum_lifting_step import drum_recover_from_over_limit
from src.steps.range_finder import turn_to_peak


class M1009TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
            Defs.pom_remover_servo.left(),
            wait_for_seconds(5),
            wall_align_forward(accel_threshold=0.7, grace_period=0.5, max_duration=2.5),
            drive_backward(cm=18),
            lineup_drum_with_pipe(False),
        ])