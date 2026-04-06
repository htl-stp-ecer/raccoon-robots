from libstp import *

from src.steps.drum_collector import eject_nearest_color


class M040EjectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # wait_for_button(),
            eject_nearest_color(),
        ])
