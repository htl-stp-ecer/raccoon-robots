from raccoon import *
from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.service.sorting_service import SortingService
from src.steps.drum_lineup_step import lineup_drum_with_pipe
from src.steps.drum_collector import drum_retreat
from src.steps.pom_pusher_servo_moves import *


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
            Defs.drum_pusher_servo.hold(),
        ])

    return defer(_build)

class M030DriveToPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # lift drum
            close_pusher_if_not_in_safe_mode(),
            Defs.lift_drums_servo.up(),

            # only continue if all drums where dispensed (failsafe)
            wait_for_checkpoint(60),

            # drive to first black line and turn
            drive_backward(heading=0).until(
                after_cm(5)
                + over_line(Defs.front_right_ir_sensor)
            ),

            pom_pusher_rubber_band_avoid_pos(),

            # turn around and then correct the heading (this instead of force dir cause its broken)
            turn_right(180),
            turn_to_heading_left(180),

            # drive to pipe
            parallel(
                drive_forward(heading=180).until(
                    after_cm(15)
                    + over_line(Defs.rear_left_ir_sensor)
                    + after_cm(1.2),
                ),
                Defs.lift_drums_servo.seek_position(30),
            ),

            background(
                pom_pusher_obstacle_avoid_pos(),
            ),

            lineup_drum_with_pipe(),
            drum_retreat(
                count=4,
                velocity_factor=0.8
            ),
        ])
