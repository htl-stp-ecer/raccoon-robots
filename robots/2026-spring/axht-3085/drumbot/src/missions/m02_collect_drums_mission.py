from libstp import *

from src.steps.debug_wait_step import debug_wait
from src.steps.drum_collector.sort_into_slot_step import sort_into_slot, go_to_empty_slot, block_timer_start, block_timer_check
from src.steps.drum_lifting_step import *
from src.steps.servo_steps import open_drum_pusher, close_drum_pusher, use_drum_to_block


@dsl
def collect_drums() -> Sequential:
    sequence = []

    start_offset = 10
    drums = 8
    time_between_drums = 7
    time_before_collecting_drum = 0.3

    def _block(checkpoint_timestamp: int, drum_number: int):
        return seq([
            debug_wait(f"Drum #{drum_number}: open pusher"),
            open_drum_pusher(),
            debug_wait(f"Drum #{drum_number}: waiting for drum..."),
            #wait_for_checkpoint(checkpoint_timestamp + time_before_collecting_drum),
            block_timer_start(),
            debug_wait(f"Drum #{drum_number}: block drum"),
            use_drum_to_block(),
            debug_wait(f"Drum #{drum_number}: align on back"),
            drum_align_on_back(),
            wait_for_seconds(0.2),
            debug_wait(f"Drum #{drum_number}: lift down"),
            drum_lifting_down(),
            debug_wait(f"Drum #{drum_number}: sort into slot"),
            sort_into_slot(),
            debug_wait(f"Drum #{drum_number}: close pusher (push into slot)"),
            close_drum_pusher(),
            debug_wait(f"Drum #{drum_number}: go to empty slot"),
            go_to_empty_slot(),         # rotate to empty slot before opening again
            block_timer_check(drum_number),
        ])

    for i in range(drums):
        timestamp = start_offset + i * time_between_drums
        sequence.append(_block(timestamp, drum_number=i + 1))

    return seq(sequence)


class M02CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drum_lifting_down(slow_mode=False),
            collect_drums(),
        ])
