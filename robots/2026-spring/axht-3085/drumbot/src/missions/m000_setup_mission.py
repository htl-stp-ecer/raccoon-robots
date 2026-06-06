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


class M000SetupMission(SetupMission):
    setup_time = 120

    def sequence(self) -> Sequential:
        return seq([
            pause_setup_timer(),
            fully_disable_servos(),

            # Camera opens once here and stays open until the shutdown mission.
            # All downstream steps (color calibration, color detection) share
            # this single USBCamera instance.
            start_camera(),

            wait_for_button("Move Servos"),
            start_setup_timer(),

            # initial servo positions
            Defs.lift_drums_servo.up(),
            Defs.pom_remover_servo.drum_moving_pos(),
            parallel(
                Defs.lift_drums_servo.down(),  # use drum_lifting_up() if motor also needs to be used
                Defs.drum_pusher_servo.open(),
            ),

            # color calibration
            parallel(
                calibrate_colors(),
                sample_drum_collector(calibration_time=5.0),
            ),
            review_drum_collector(review_delta=750),
            align_edge(),

            # distance sensor calibration
            # TODO: check if still needed
            # drum_seek(),
            # Defs.pom_remover_servo.left(),
            # calibrate_analog_sensor(Defs.et_range_finder),

            Defs.lift_drums_servo.up(),

            calibrate(
                distance_cm=50,
                speed=0.5,
                exclude_ir_sensors=[
                    Defs.wait_for_light_sensor,
                    Defs.drum_light_sensor,
                ],
            ),
        ])
