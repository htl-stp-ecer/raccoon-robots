from raccoon import *

from src.steps.collect_drums_step import collect_drums
from src.steps.drum_collector import go_to_empty_slot_plus_one


class M020CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            collect_drums(),
            Defs.drum_pusher_servo.close(),
            go_to_empty_slot_plus_one(),
        ])
