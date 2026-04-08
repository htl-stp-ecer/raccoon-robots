from libstp import dsl, seq, turn_left, drive_to_analog_target, drive_forward

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_seek, drum_eject_position
from src.steps.range_finder import turn_to_peak


@dsl
def lineup_drum_with_pipe():
    return seq([
        drum_seek(),
        turn_to_peak(turn_speed=0.4),
        turn_left(2.5, 1),

        # drive_forward().until(on_analog_above(Defs.IR_Distanz_to_pipe_sensor, 2300)),
        drive_to_analog_target(Defs.et_range_finder, 0.2),
        #drive_forward(2.5),
        # drive_to_analog_target(Defs.et_range_finder),
        # wall_align_forward(speed=1, accel_threshold=0.35, settle_duration=0, max_duration=2, grace_period=0.25),
        # parallel(
        # drive_backward(3.3, 1),
        # drive_forward(3,1),
        drum_eject_position()
    ])
# ),
