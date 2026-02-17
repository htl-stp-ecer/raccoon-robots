from libstp import *
from src.hardware.defs import *
from src.steps.servo_steps import *


class SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(cm=50),
            turn_left(degrees=90),
            #set servos to start pos
            # servo_pom_arm_start(),
            # servo_pom_grab_start(),
            # servo_shild_down(),
            #
            # calibrate(distance_cm=50),
            wait_for_button(),

            #calibrate_wait_for_light(Defs.wait_for_light_sensor),
        ])
