
from raccoon import *

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.steps.collect_drums_step import collect_drums
from src.steps.drum_lifting_step import drum_lifting_up


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
            Defs.drum_pusher_servo.close(),
        ])

    return defer(_build)


class M020CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            wait_for_background("lower_drum"),
            collect_drums(),
            mark_heading_reference(),
            after_collect(),
        ])
