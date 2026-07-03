from raccoon import *
from os import getenv

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.steps.collect_drums_step import collect_drums
from src.steps.drum_lifting_step import drum_lifting_up
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
            settle_duration=9999,
            max_duration=9999,
            grace_period=9998,
        ),
    ])


class M020CollectDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # drive against pipe to align while lowering drum and starting drum collection
            # position holding waits for this background task to finish to avoid this wall_align and the one in
            # the position hold step conflicting
            background(
                seq([
                    wall_align_forward(
                        accel_threshold=0.4,
                        grace_period=0.5,
                        max_duration=1.5,
                    ),
                    mark_heading_reference(),
                ]),
                name="before_collect_align"
            ),

            parallel(
                Defs.lift_drums_servo.down(),
                Defs.drum_pusher_servo.open(),
            ),
            # terminate_leftover_velocity(),

            # drive_forward(3,1),
            # wait_for_background("lower_drum"),

            # set_position_hold_velocity(),
            do_while_active(
                reference_step=collect_drums(),
                task=collect_position_hold(),
            ),
            # terminate_leftover_velocity(),

            # re-mark heading reference (because of static imu drift)
            mark_heading_reference(),
            after_collect(),
        ])
