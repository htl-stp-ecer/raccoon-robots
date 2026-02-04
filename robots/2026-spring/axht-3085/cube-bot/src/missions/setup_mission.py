from libstp import *
from src.hardware.defs import *
from src.steps.servo_steps import *


class SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #set servos to start pos
            servo_pom_arm_start(),
            servo_pom_grab_close(),

            calibrate_distance(distance_cm=50, calibrate_light_sensors=True),
            wait_for_button(),
            #calibrate_wait_for_light(Defs.wait_for_light_sensor),
        ])
