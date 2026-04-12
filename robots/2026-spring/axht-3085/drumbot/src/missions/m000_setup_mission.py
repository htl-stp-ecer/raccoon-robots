from raccoon import *
from raccoon.step.sequential import *

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
            start_setup_timer(),  # countdown begins here, full duration

            Defs.pom_remover_servo.start(),

            #color calibration
            Defs.drum_pusher_servo.open(),
            drum_lifting_down(),
            parallel(
                calibrate_colors(),
                sample_drum_collector(calibration_time=5.0),
            ),
            review_drum_collector(review_delta=750),
            align_edge(),

            #distance sensor calibration
            drum_seek(),
            calibrate_analog_sensor(Defs.et_range_finder),

            wait_for_button("Move Drum over limit"),
            drum_lifting_up_over_limit(),

            calibrate(distance_cm=50, speed=0.5, exclude_ir_sensors=[
                Defs.wait_for_light_sensor,
                Defs.drum_light_sensor,
            ]),

        ])