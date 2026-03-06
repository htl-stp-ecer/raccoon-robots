from libstp import *
from src.hardware.defs import *
from src.steps.servo_steps import *
from src.steps.light_sensor_steps import frontside_line_follow_right_edge
from src.steps.light_sensor_steps import single_line_follow_right_front_edge_until_line


class M01SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #set servos to start pos
            parallel(
                servo_pom_arm_start(),
                servo_pom_grab_start(),
                servo_shield_down(),
                servo_shield_grabber_close(),
            ),

            calibrate(distance_cm=50,
                      calibration_sets=["default", "upper"],
                      ),

            switch_calibration_set("upper"),

        ])
