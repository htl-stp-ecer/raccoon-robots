from libstp import seq, Mission, wait_for_checkpoint, wait_for_button, loop_forever, slow_servo

from src.steps.drum_collector import drum_retreat
from src.steps.drum_pusher_servo import open_drum_pusher, close_drum_pusher


class PotatoMission(Mission):
    def sequence(self) -> "Step":
        return seq([
            loop_forever(seq([
                open_drum_pusher(),
                 wait_for_button(),
                # wait_for_checkpoint(11),
                close_drum_pusher(),
                drum_retreat(),

            ])),

        ])
