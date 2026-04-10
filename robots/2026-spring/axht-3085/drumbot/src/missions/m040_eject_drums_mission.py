from raccoon import *

from src.steps.drum_collector import eject_nearest_color


class M040EjectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            eject_nearest_color(),
        ])
