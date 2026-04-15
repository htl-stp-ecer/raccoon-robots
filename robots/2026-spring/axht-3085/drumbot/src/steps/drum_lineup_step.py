from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_seek, drum_eject_position, drum_recover_from_over_limit
from src.steps.range_finder import turn_to_peak


@dsl
def lineup_drum_with_pipe(recover_from_limit: bool = False):
    drum_servo_step = drum_recover_from_over_limit(
        Defs.lift_drums_servo.seek_position) if recover_from_limit else drum_seek()
    return seq([
        # drum_servo_step,
        Defs.lift_drums_servo.seek_position(),
        wait_for_seconds(0.5),  # wait so our drum is on seek position
        turn_right(30),
        drive_forward(speed=0.2).until(on_digital(Defs.drum_found_button)),
        drum_eject_position(),
        #drive_forward(4.1, speed=0.5),
    ])
    # ),
