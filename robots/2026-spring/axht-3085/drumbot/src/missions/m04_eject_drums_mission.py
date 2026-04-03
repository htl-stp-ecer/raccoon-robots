from libstp import *

from src.steps.drum_collector import eject_nearest_color


@dsl
def eject_drums() -> Sequential:
    return seq([
        eject_nearest_color(),
    ])


class M04EjectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #wait_for_button(),
            eject_drums(),
        ])
