from raccoon import *

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.steps.collect_drums_step import collect_drums
from src.steps.drum_lifting_step import drum_lifting_up
from src.steps.drum_collector import rotate_to_eject_start, drum_retreat
from src.steps.terminate_leftover_velocity import terminate_leftover_velocity
from src.steps.set_position_hold_velocity_step import set_position_hold_velocity

@dsl
def after_collect():
    def _build(robot: "Robot"):
        drum_service = robot.get_service(DrumMotorService)

        if drum_service.collection_failed:
            drum_service.warn("Safe mode — lifting drum collector and skipping post-collection steps")
            return seq([
                drum_lifting_up(always_motor_support=True),
            ])

        # Region 0-3 → retreat 1 slot, region 4-7 → retreat 2 slots.
        retreat_count = 1 if drum_service.current_pocket <= 3 else 2

        return seq([
            Defs.drum_pusher_servo.hold(),
            drum_retreat(retreat_count),
            # rotate_to_eject_start(),
        ])

    return defer(_build)


class M020CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            wait_for_background("lower_drum"),
            terminate_leftover_velocity(),

            set_position_hold_velocity(),
            collect_drums(),
            terminate_leftover_velocity(),

            mark_heading_reference(),
            after_collect(),
        ])
