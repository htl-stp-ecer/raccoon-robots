from libstp import *
from libstp.mission.api import *
from libstp.step.sequential import *

from src.hardware.defs import *
from src.steps.drum_collector import calibrate_drum_collector, drum_retreat
from src.steps.drum_lifting_step import drum_lifting_down, drum_lifting_up
from src.steps.range_finder import calibrate_range_finder
from src.steps.servo_steps import *
from src.steps.debug_wait_step import debug_wait
from src.steps.drive_to_pipe import drive_to_first_pipe, drive_to_second_pipe


class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # auto_tune(
            #    characterize_axes=[ "angular"],
            #    vel_axes=[ "wz"],
            #    motion_axes=["distance", "heading"],
            # ),
            wait_for_button(),
            drum_lifting_up(slow_mode=False),
            calibrate(distance_cm=50, exclude_ir_sensors=[
                Defs.wait_for_light_sensor,
                Defs.drum_light_sensor,
            ]),

            # Drives to black and hardcoded cm forward
            debug_wait("Place on black tape for seed first pipe position"),
            drive_to_first_pipe(),
            calibrate_range_finder(turn_speed=0.2, profile="first_pipe"),

            # Follows line until at the second pipe
            debug_wait("Place at the seed position for second pipe"),
            drive_to_second_pipe(),
            calibrate_range_finder(turn_speed=0.2, profile="second_pipe"),

            wait_for_button(),
            open_drum_pusher(),
            drum_lifting_down(),
            calibrate_drum_collector(calibration_time=2.0),
            drum_retreat(),
            set_motor_velocity(Defs.drum_motor, -830),
            wait_for_seconds(0.3),
            motor_passive_brake(Defs.drum_motor),
            driving_position_pom_remover_servo(),

        ])
