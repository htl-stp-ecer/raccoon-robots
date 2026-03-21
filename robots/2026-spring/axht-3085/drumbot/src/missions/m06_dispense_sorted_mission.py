from libstp import *

from src.steps.drum_collector.dispense_sorted_step import dispense_sorted
from src.steps.drum_lifting_step import shake_drums


class M06DispenseSortedMission(Mission):
    """Dispense sorted drums: first all blue, then all pink."""

    def sequence(self) -> Sequential:
        return seq([
            shake_drums(),
            dispense_sorted("blue"),
            dispense_sorted("pink"),
        ])
