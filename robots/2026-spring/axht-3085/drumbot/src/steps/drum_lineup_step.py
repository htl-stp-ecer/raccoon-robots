from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_seek, drum_eject_position
from src.steps.range_finder import turn_to_peak


@dsl
def lineup_drum_with_pipe():
    return seq([
        drum_seek(),
        timeout(
            step=seq([
                turn_to_peak(
                    turn_speed=0.6,
                    sweep_speed=40,
                    ),
                turn_left(2), #hardcoded magic value so we are aligned on pipe
                drive_to_analog_target(Defs.et_range_finder, 0.2),
            ]),
            seconds=6,
        ),

        drum_eject_position()
    ])
# ),
