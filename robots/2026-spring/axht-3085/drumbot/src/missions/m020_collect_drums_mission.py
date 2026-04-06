from libstp import *

from src.steps.collect_drums_step import collect_drums
from src.steps.drum_collector import drum_advance
from src.steps.servo_steps import close_drum_pusher


class M020CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            collect_drums(),
            close_drum_pusher(),
            drum_advance(),
            # advance_to_midpoint()
        ])
