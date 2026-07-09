from raccoon import *
from os import getenv

from raccoon.robot.heading_reference import HeadingReferenceService

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.steps.collect_drums_step import collect_drums
from src.steps.drum_collector.go_to_slot_step import go_to_slot

POSITION_HOLD_ENV = "DRUMBOT_NO_POSITION_HOLD"
HEADING_MARK_TOLERANCE_DEG = 3.0
_was_first_heading_valid = True


@dsl
def after_collect():
    def _build(robot: "Robot"):
        drum_service = robot.get_service(DrumMotorService)
        stall_retries = 3

        if drum_service.collection_failed:
            drum_service.warn("Safe mode — lifting drum collector and skipping post-collection steps")
            stall_retries = 1
            # Enter the eject phase now so the emergency nav-lock is dropped
            # *before* the slot-2 alignment runs. Without this, motor_locked
            # makes go_to_pocket early-return and the revolver never even
            # attempts to reach slot 2 — the eject then starts from wherever
            # the emergency left it (2 pockets off), so nothing lands on the
            # pipe. begin_eject picks the retry budget by cause; combined with
            # go_to_slot's tolerate_stall=True below, a genuinely faulted motor
            # still gets exactly one careful attempt, then brakes and continues.
            drum_service.begin_eject()

        return seq([
            parallel(
                Defs.drum_pusher_servo.hold(),
                go_to_slot(2, stall_retries=stall_retries, tolerate_stall=True),
            ),
            Defs.lift_drums_servo.up(),
        ])

    return defer(_build)

def collect_position_hold():
    if getenv(POSITION_HOLD_ENV) is not None: return run(lambda robot: None)
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

def drum_pipe_heading_mark_one():
    def _build(robot: "Robot"):
        global _was_first_heading_valid

        heading_service = robot.get_service(HeadingReferenceService)
        error_deg = heading_service.current_relative_deg()

        if abs(error_deg) > HEADING_MARK_TOLERANCE_DEG:
            heading_service.warn(
                f"Skipping heading reference mark — error {error_deg:.1f}° "
                f"exceeds tolerance {HEADING_MARK_TOLERANCE_DEG:.1f}°"
            )
            _was_first_heading_valid = False
            return run(lambda robot: None)
        return mark_heading_reference()

    return defer(_build)


def drum_pipe_heading_mark_two():
    def _build(robot: "Robot"):
        global _was_first_heading_valid
        if not _was_first_heading_valid:
            robot.get_service(HeadingReferenceService).warn(
                "[drum_pipe_heading_mark_two] skipping mark_heading_reference - invalid orientation"
            )
            return run(lambda robot: None)
        return mark_heading_reference()

    return defer(_build)


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
                        grace_period=1.0,
                        max_duration=2.0,
                    ),
                    drum_pipe_heading_mark_one(),
                ]),
                name="before_collect_align"
            ),

            # lower drum
            parallel(
                Defs.lift_drums_servo.down(),
                Defs.drum_pusher_servo.open(),
            ),

            # collect drums + position hold
            do_while_active(
                reference_step=collect_drums(),
                task=collect_position_hold(),
            ),

            # re-mark heading reference (because of static imu drift)
            drum_pipe_heading_mark_two(),
            after_collect(),
        ])
