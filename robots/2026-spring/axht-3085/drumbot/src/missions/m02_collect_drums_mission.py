from libstp import *

from src.steps.collect_drums_step import collect_drums
from src.steps.drum_collector.sort_into_slot_step import advance_to_midpoint


class M02CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            collect_drums(),
            advance_to_midpoint(),
        ])
