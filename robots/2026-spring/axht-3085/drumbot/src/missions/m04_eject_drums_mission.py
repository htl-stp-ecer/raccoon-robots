from libstp import *

from src.steps.drum_collector import drum_retreat


@dsl
def eject_drums() -> Sequential:
    sequence = []
    drums = 1

    def _block():
        return seq([
            drum_retreat(),
        ])

    for _i in range(drums):
        sequence.append(_block())

    return seq(sequence)


class M04EjectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #wait_for_button(),
            eject_drums(),
            eject_drums(),
            eject_drums(),
            eject_drums(),
            #eject_drums(),
        ])
