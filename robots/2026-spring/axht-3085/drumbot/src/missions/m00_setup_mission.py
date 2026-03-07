from src.steps.drum_collector import calibrate_drum_collector
from src.steps.drum_lifting_step import *
from src.steps.drum_pusher_servo import open_drum_pusher


class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            open_drum_pusher(),
            #drum_lifting_up(slow_mode=False),
            # calibrate(distance_cm=50, exclude_ir_sensors=[
            #     Defs.wait_for_light_sensor,
            #     Defs.drum_light_sensor
            # ]),
            # drum_lifting_down(),
            calibrate_drum_collector(calibration_time=2.0),
        ])
