from libstp import *
from libstp.step.sequential import *

from src.steps.camera_lifecycle_step import start_camera
from src.steps.color_calibration import calibrate_colors
from src.steps.debug_wait_step import debug_wait
from src.steps.drum_collector import align_edge, calibrate_drum_collector
from src.steps.drum_lifting_step import drum_lifting_down, drum_lifting_up, drum_seek
from src.steps.servo_steps import *


class M000SetupMission(SetupMission):
    def sequence(self) -> Sequential:
        return seq([
            fully_disable_servos(),
            wait_for_button(),

            drum_lifting_up(slow_mode=False),
            Defs.pom_remover_servo.start(),

            calibrate(distance_cm=50, exclude_ir_sensors=[
                Defs.wait_for_light_sensor,
                Defs.drum_light_sensor,
            ]),


            # Drives to black and hardcoded cm forward
            drum_seek(),
            calibrate_analog_sensor(Defs.et_range_finder),
            wait_for_button(),
            drum_lifting_down(),
            open_drum_pusher(),
            calibrate_colors(),
            wait_for_button(),
            start_camera(),
            calibrate_drum_collector(calibration_time=5.0),
            align_edge(),
        ])