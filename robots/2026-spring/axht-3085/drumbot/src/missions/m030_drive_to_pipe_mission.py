from raccoon import *

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.service.sorting_service import SortingService
from src.steps.drum_lifting_step import drum_lifting_up, drum_lifting_up_over_limit
from src.steps.drum_lineup_step import lineup_drum_with_pipe
from src.steps.drum_lifting_step import drum_recover_from_over_limit


def print_debug_info(robot):
    drum = robot.get_service(DrumMotorService)
    sorting = robot.get_service(SortingService)
    info(f"[DEBUG] Current pocket: {drum.current_pocket}")
    info(f"[DEBUG] Slots: {sorting.slots}")
    info(f"[DEBUG] Blue slots: {sorting.blue_slots}  (next: {sorting.blue_next})")
    info(f"[DEBUG] Pink slots: {sorting.pink_slots}  (next: {sorting.pink_next})")
    info(f"[DEBUG] Empty slot: {sorting.empty_slot}")


class M030DriveToPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # lift drum
            Defs.drum_pusher_servo.close(),
            drum_lifting_up_over_limit(),

            wait_for_checkpoint(60),  # only continue if we all drums where dispenced (fail save)

            # drive to first black line and turn
            parallel(
                drive_backward().until(
                    over_line(Defs.front_right_ir_sensor)
                ),
                #seq([
                #    wait_until_distance(6),
                #
                #]),
            ),
            turn_to_heading_left(180),

            # drive to pipe
            parallel(
                drive_forward().until(
                    over_line(Defs.front_right_ir_sensor) +
                    after_cm(18)
                ),
            ),

            background(Defs.pom_remover_servo.center()),
            drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
            drive_forward(cm=5),
            lineup_drum_with_pipe(False),



            # eject drum mission will be executed next
        ])
