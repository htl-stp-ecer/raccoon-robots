from raccoon import dsl, seq, turn_left, drive_to_analog_target, drive_forward

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_seek, drum_eject_position
from src.steps.range_finder import turn_to_peak


@dsl
def lineup_drum_with_pipe():
    return seq([
        drum_seek(),
        turn_to_peak(turn_speed=0.6),
        drive_to_analog_target(Defs.et_range_finder, 0.2),
        drum_eject_position()
    ])
# ),
