from libstp import *

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.steps.drum_collect_retry_step import drum_motor_turn_with_retry
from src.steps.drum_lifting_step import drum_lifting_down
from src.steps.servo_steps import open_drum_pusher, close_drum_pusher


@dsl
def collect_drums(offset_velocity: int = -830, offset_time: float = 0.3,) -> Sequential:
    sequence = []

    start_offset = 10
    drums = 8
    time_between_drums = 7
    time_before_collecting_drum = 0.8

    def _block(checkpoint_timestamp: int, time_budget: float):
        def _build(robot):
            service = robot.get_service(DrumMotorService)
            if service.collection_failed:
                info("Skipping drum collection — system is in safe mode")
                return seq([])
            return seq([
                open_drum_pusher(),
                wait_for_checkpoint(checkpoint_timestamp + time_before_collecting_drum),
                close_drum_pusher(),
                drum_motor_turn_with_retry(
                    time_budget=time_budget,
                    offset_velocity=offset_velocity,
                    offset_time=offset_time,
                ),
            ])
        return defer(_build)

    for i in range(drums):
        timestamp = start_offset + i * time_between_drums
        # time budget = seconds until the *next* drum needs to be collected
        # last drum gets the full window since there's no next one
        remaining = time_between_drums - time_before_collecting_drum
        sequence.append(_block(timestamp, remaining))

    return seq(sequence)


class M02CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drum_lifting_down(slow_mode=False),
            collect_drums(),
        ])
