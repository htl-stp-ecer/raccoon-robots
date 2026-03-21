from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import *
from src.steps.servo_steps import open_drum_pusher, close_drum_pusher, use_drum_to_block


@dsl
def collect_drums(offset_velocity: int = -830, offset_time: float = 0.3,) -> Sequential:
    sequence = []

    start_offset = 10
    drums = 8
    time_between_drums = 7
    time_before_collecting_drum = 0.3

    def _block(checkpoint_timestamp: int):
        return seq([
            open_drum_pusher(),
            wait_for_checkpoint(checkpoint_timestamp + time_before_collecting_drum),
            use_drum_to_block(),
            drum_align_on_back(),
            wait_for_seconds(0.2),
            drum_lifting_down(),
            close_drum_pusher(),
            wait_for_seconds(0.2),
            drum_retreat(),
            # relative soon
            set_motor_velocity(Defs.drum_motor, offset_velocity),
            wait_for_seconds(offset_time),
            motor_passive_brake(Defs.drum_motor),
        ])

    for i in range(drums):
        timestamp = start_offset + i * time_between_drums
        sequence.append(_block(timestamp))

    return seq(sequence)


class M02CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drum_lifting_down(slow_mode=False),
            collect_drums(),
        ])
