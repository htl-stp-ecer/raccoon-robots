from libstp import *
from libstp.mission.api import *
from libstp.step.sequential import *

from src.hardware.defs import *
from src.steps.drum_collector import calibrate_drum_collector
from src.steps.drum_lifting_step import drum_lifting_up, drum_lifting_down
from src.steps.servo_steps import open_drum_pusher
from src.steps.range_finder import *


class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            wait_for_button(),
            drum_lifting_up(slow_mode=False),
            wait_for_button(),
            calibrate_range_finder(),
            open_drum_pusher(),

             calibrate(distance_cm=50, exclude_ir_sensors=[
                 Defs.wait_for_light_sensor,
                 Defs.drum_light_sensor
             ]),
            drum_lifting_down(),
            calibrate_drum_collector(calibration_time=2.0),
        ])
