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

            wait_for_checkpoint(60),  # only continue if we all drums where dispenced (fail save)
            # ToDo: Detect pom infront of it
            # mark_heading_reference(
            #     origin_offset_deg=90,
            # ),

            # drive to first black line and turn
            #parallel(
            drive_backward(5),
            turn_to_heading_right(0),
                drive_backward().until(
                    over_line(Defs.front_right_ir_sensor)
                ),
                #seq([
                #    wait_until_distance(6),
                #
                #]),
            #),
            turn_to_heading_left(178), #turn a bit less than 180° to make sure we stand as close as possible to the pipe

            # drive to pipe
            parallel(
                seq([
                    drive_forward(speed=0.7).until(
                        after_cm(20) +
                        over_line(Defs.front_left_ir_sensor)
                    ),
                ]),
                seq([
                    wait_for_checkpoint(15),
                    drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
                ])
            ),

            #background(Defs.pom_remover_servo.center()),

            #drive_forward(cm=8, speed=0.35),
            # TODO: Test this shit
            #wall_align_forward(accel_threshold=10.0, grace_period=0.5, max_duration=2.5),
            #drive_backward(cm=16),
            lineup_drum_with_pipe(),
            # eject drum mission will be executed next
        ])
