from libstp import *

from src.steps.debug_wait_step import debug_wait
from src.steps.drum_collector.sort_into_slot_step import (
    advance_to_midpoint,
    block_timer_check,
    block_timer_start,
    go_to_empty_slot,
    sort_into_slot,
)
from src.steps.drum_lifting_step import *
from src.steps.servo_steps import close_drum_pusher, open_drum_pusher, use_drum_to_block


@dsl
def collect_drums() -> Sequential:
    sequence = []

    start_offset = 10
    drums = 8
    time_between_drums = 7

    def _block(checkpoint_timestamp: int, drum_number: int):
        return seq([
            open_drum_pusher(),
            #debug_wait(f"Drum #{drum_number}: waiting for drum..."),
            #wait_for_checkpoint(checkpoint_timestamp + time_before_collecting_drum),
            debug_wait(f"Drum #{drum_number}: block drum"),
            block_timer_start(),

            parallel(
                use_drum_to_block(),
                advance_to_midpoint(),
            ),

            drum_align_on_back(),

            parallel(
                drum_lifting_down(),
                sort_into_slot(),
            ),
            # sort_into_slot auto-accounts for midpoint offset — no retreat needed
            close_drum_pusher(),
            go_to_empty_slot(),
            #advance_to_midpoint(),
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
            advance_to_midpoint(),
        ])
