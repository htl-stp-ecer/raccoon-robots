from raccoon import *

from src.steps.camera_lifecycle_step import start_camera
from src.steps.color_calibration import calibrate_colors
from src.steps.drum_collector import (
    align_edge,
    review_drum_collector,
    sample_drum_collector,
)
from src.steps.drum_lifting_step import *
from src.hardware.defs import Defs
from src.steps.drum_collector.pocket_jog_step import pocket_jog
from src.steps.position_hold_choice_step import choose_position_hold


class M000SetupMission(SetupMission):
    setup_time = 90

    def sequence(self) -> Sequential:
        return seq([
            pause_setup_timer(),

            # Ask up front whether to use position holding during collection.
            # Sets/clears DRUMBOT_NO_POSITION_HOLD for the rest of the run.
            choose_position_hold(),

            fully_disable_servos(),

            # Camera opens once here and stays open until the shutdown mission.
            # All downstream steps (color calibration, color detection) share
            # this single USBCamera instance.
            start_camera(),

            wait_for_button("Move Servos"),
            start_setup_timer(),

            # initial servo positions
            parallel(
                Defs.lift_drums_servo.up(),
                Defs.pom_remover_servo.drum_moving_pos(),
                Defs.drum_pusher_servo.block_angle(),
            ),

            # ir + distance calibration
            run_unless_no_calibrate(
                seq([
                    wait_for_button("Press the button to start calibration (distance + ir sensor, 70cm)"),
                    mark_heading_reference(),
                    collect_drive(
                        collect_ir_set(
                            drive_forward(70),
                            set_name="default",
                            sensors=[Defs.front_right_ir_sensor, Defs.rear_left_ir_sensor]
                        )
                    ),

                    calibration_gate(
                        require_axes=[CalibrationAxis.FORWARD],
                        require_ir_sets=["default"],
                    ),
                ]),
            ),

            # color calibration
            parallel(
                Defs.lift_drums_servo.down(),
                Defs.drum_pusher_servo.open(),
            ),
            parallel(
                run_unless_no_calibrate(
                    calibrate_colors(),
                ),
                sample_drum_collector(calibration_time=5.0),
            ),
            review_drum_collector(review_delta=750),
            align_edge(),

            parallel(
                Defs.lift_drums_servo.over_limit(),
                Defs.drum_pusher_servo.block_angle(),
            ),

            wait_for_button("Set Pom Pusher Servo"),
            Defs.pom_remover_servo.right(),

            fully_disable_servos(),
        ])
