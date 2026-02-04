from libstp import *
from src.hardware.defs import *
from src.steps.servo_steps import *


class SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #set servos to start pos
            servo_pom_arm_start(),
            servo_pom_grab_close(),

            calibrate_distance(),
            calibrate_sensors(calibration_time=5),
            wait_for_button(),
            #calibrate_wait_for_light(Defs.wait_for_light_sensor),
        ])
