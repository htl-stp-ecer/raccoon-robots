from libstp import *
from libstp.step.sequential import *

from src.steps.camera_lifecycle_step import start_camera
from src.steps.color_calibration import calibrate_colors
from src.steps.debug_wait_step import debug_wait
from src.steps.drive_to_pipe import drive_to_first_pipe
from src.steps.drum_collector import align_edge, calibrate_drum_collector
from src.steps.drum_lifting_step import drum_lifting_down, drum_lifting_up
from src.steps.range_finder import calibrate_range_finder
from src.steps.servo_steps import *


class M00SetupMission(SetupMission):
    def sequence(self) -> Sequential:
        return seq([
            wait_for_button(),
            Defs.pom_remover_servo.start(),
            drum_lifting_up(slow_mode=False),
            calibrate(distance_cm=50, exclude_ir_sensors=[
                Defs.wait_for_light_sensor,
                Defs.drum_light_sensor,
            ]),

            # Drives to black and hardcoded cm forward
            calibrate_range_finder(sweep_deg=45,
                                   turn_speed=0.2,
                                   profile="first_pipe",
                                   setup_steps=[
                debug_wait("Place on black tape for seed first pipe position"),
                drive_to_first_pipe(),
            ]),

            # Follows line until at the second pipe
            # calibrate_range_finder(turn_speed=0.2, profile="second_pipe", setup_steps=[
            #     debug_wait("Place at the seed position for second pipe"),
            #     drive_to_second_pipe(),
            # ]),

            drum_lifting_down(),
            open_drum_pusher(),
            calibrate_colors(),
            wait_for_button(),
            start_camera(),
            calibrate_drum_collector(calibration_time=5.0),
            align_edge(),
        ])