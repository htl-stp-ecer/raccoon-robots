from raccoon import *

from src.steps.drum_collector import eject_nearest_color


class MEjectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            eject_nearest_color(),
            drive_forward(10)
        ])
