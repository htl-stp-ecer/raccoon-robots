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
        timeout_or(
            step=seq([
                turn_to_peak(
                    turn_speed=0.3,
                    sweep_deg=40,
                ),
            ]),
            seconds=4,
            fallback=seq([
                drive_backward(cm=7),
                turn_left(degrees=10),
                turn_to_peak(
                    turn_speed=0.6,
                    sweep_deg=40,
                ),
            ]),
        ),
        timeout(
            step=seq([
                turn_left(1.5, speed=0.3),  # hardcoded magic value so we are aligned on pipe
                drive_to_analog_target(Defs.et_range_finder, 0.2),
            ]),
            seconds=4,
        ),
        drum_eject_position(),
        drive_forward(4.5, speed=0.5),
    ])
    # ),
