from raccoon import *

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.service.sorting_service import SortingService
from src.steps.drum_lifting_step import drum_lifting_up_over_limit
from src.steps.drum_lineup_step import lineup_drum_with_pipe
from src.steps.drum_lifting_step import drum_recover_from_over_limit
from src.steps.drum_collector import eject_nearest_color


def print_debug_info(robot):
    drum = robot.get_service(DrumMotorService)
    sorting = robot.get_service(SortingService)
    info(f"[DEBUG] Current pocket: {drum.current_pocket}")
    info(f"[DEBUG] Slots: {sorting.slots}")
    info(f"[DEBUG] Blue slots: {sorting.blue_slots}  (next: {sorting.blue_next})")
    info(f"[DEBUG] Pink slots: {sorting.pink_slots}  (next: {sorting.pink_next})")


@dsl
def close_pusher_if_not_in_safe_mode():
    def _build(robot: "Robot"):
        drum_service = robot.get_service(DrumMotorService)

        if drum_service.collection_failed:
            drum_service.warn("Safe mode — lifting drum collector and skipping post-collection steps")
            return seq([])

        return seq([
            Defs.drum_pusher_servo.close(),
        ])

    return defer(_build)

class M030DriveToPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # lift drum
            close_pusher_if_not_in_safe_mode(),
            drum_lifting_up_over_limit(),

            # only continue if all drums where dispensed (failsafe)
            wait_for_checkpoint(60),

            # drive to first black line and turn
            drive_backward(5),
            turn_to_heading_right(0),
            drive_backward().until(
                over_line(Defs.front_right_ir_sensor)
            ),
            turn_to_heading_left(178), # turn a bit less than 180° to make sure we stand as close as possible to the pipe

            # drive to pipe
            parallel(
                seq([
                    drive_forward(speed=0.7).until(
                        after_cm(20) +
                        over_line(Defs.rear_left_ir_sensor)
                    ),
                ]),
                seq([
                    wait_for_checkpoint(15),
                    drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
                ])
            ),

            lineup_drum_with_pipe(),
            eject_nearest_color(),
        ])
