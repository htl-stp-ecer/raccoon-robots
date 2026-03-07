from libstp import *

from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_down
from src.steps.drum_pusher_servo import open_drum_pusher, close_drum_pusher


class M02CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drum_lifting_down(slow_mode=False),
            open_drum_pusher(),
            wait_for_checkpoint(11),
            close_drum_pusher(),
            drum_retreat(),
        ])
