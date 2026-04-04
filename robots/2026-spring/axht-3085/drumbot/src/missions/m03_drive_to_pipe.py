from libstp import *

from src.steps.drive_to_pipe import drive_to_first_pipe
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_up, drum_eject_position, drum_lifting_remove_D, \
    drum_lifting_remove_M, drum_seek
from src.steps.range_finder import turn_to_peak
from src.hardware.defs import Defs
from src.steps.servo_steps import close_drum_pusher
from src.service.drum_motor_service import DrumMotorService
from src.service.sorting_service import SortingService

def print_debug_info(robot):
    drum = robot.get_service(DrumMotorService)
    sorting = robot.get_service(SortingService)
    info(f"[DEBUG] Current pocket: {drum.current_pocket}")
    info(f"[DEBUG] Slots: {sorting.slots}")
    info(f"[DEBUG] Blue slots: {sorting.blue_slots}  (next: {sorting.blue_next})")
    info(f"[DEBUG] Pink slots: {sorting.pink_slots}  (next: {sorting.pink_next})")
    info(f"[DEBUG] Empty slot: {sorting.empty_slot}")

class M03DriveToPipe(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #drum_retreat(),

            #drive to first black line and turn
            close_drum_pusher(),
            drum_lifting_up(),
            drive_backward().until(
                on_black(Defs.front_right_ir_sensor) >
                after_cm(7)
            ),
            turn_to_heading_left(90),

            drive_to_first_pipe(),

            drum_seek(),
            turn_to_peak(turn_speed=0.4, profile="first_pipe"),
            turn_left(3.5, 1),

            #drive_to_analog_target(Defs.et_range_finder),
            wall_align_forward(speed=0.3, accel_threshold=0.3, settle_duration=0.2, max_duration=3, grace_period=0.4),
            parallel(
                drive_backward(3.3, 1),
                drum_eject_position()
            ),

        ])
