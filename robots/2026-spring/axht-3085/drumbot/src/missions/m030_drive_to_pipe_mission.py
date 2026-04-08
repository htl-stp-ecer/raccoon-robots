from libstp import *

from src.hardware.defs import Defs
from src.service.drum_motor_service import DrumMotorService
from src.service.sorting_service import SortingService
from src.steps.drive_to_pipe import drive_to_first_pipe
from src.steps.drum_lifting_step import drum_lifting_up
from src.steps.servo_steps import close_drum_pusher
from src.steps.drum_lineup_step import lineup_drum_with_pipe


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
            # drum_retreat(),

            # drive to first black line and turn
            close_drum_pusher(),
            drum_lifting_up(),
            drive_backward().until(
                on_black(Defs.front_right_ir_sensor) >
                after_cm(7)
            ),
            turn_to_heading_left(90),

            drive_to_first_pipe(),
            lineup_drum_with_pipe(),
        ])
