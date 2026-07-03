from raccoon import *
from os import getenv

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.steps.collect_drums_step import collect_drums
from src.steps.drum_lifting_step import drum_lifting_up
from src.steps.terminate_leftover_velocity import terminate_leftover_velocity
from src.steps.set_position_hold_velocity_step import set_position_hold_velocity
from src.steps.drum_collector.go_to_slot_step import go_to_slot


@dsl
def after_collect():
    def _build(robot: "Robot"):
        drum_service = robot.get_service(DrumMotorService)

        if drum_service.collection_failed:
            drum_service.warn("Safe mode — lifting drum collector and skipping post-collection steps")
            return seq([
                drum_lifting_up(always_motor_support=True),
            ])

        return seq([
            Defs.drum_pusher_servo.hold(),
            go_to_slot(2),
            # rotate_to_eject_start(),
        ])

    return defer(_build)

def collect_position_hold():
    if getenv("DRUMBOT_NO_POSITION_HOLD") is not None: return run(lambda robot: None)
    return seq([
        # wait for aligning while starting collection to avoid the wall aligns conflicting
        wait_for_background("before_collect_align"),
        wall_align_forward(
            speed=0.2,
            accel_threshold=99,
            settle_duration=0,
            max_duration=1,
            grace_period=99999,
        ),
    ])


class M020CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(3,1),
            wait_for_background("lower_drum"),
            terminate_leftover_velocity(),

            set_position_hold_velocity(),
            do_while_active(
                reference_step=collect_drums(),
                task=collect_position_hold(),
            ),
            terminate_leftover_velocity(),

            mark_heading_reference(),
            after_collect(),
        ])
