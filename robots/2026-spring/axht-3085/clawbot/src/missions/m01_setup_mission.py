from libstp import *
from src.hardware.defs import *
from src.steps.light_sensor_steps import frontside_forward_lineup_on_black, frontside_line_follow_right_edge
from src.steps.servo_steps import *
from src.steps.single_line_follow import follow_line_single_right_edge


class M01SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #set servos to start pos
            servo_pom_arm_start(),
            servo_pom_grab_start(),
            servo_shild_down(),
            servo_shild_grabber_close(),

            calibrate(distance_cm=50),
            stop(),
            wait_for_button(),
            frontside_line_follow_right_edge(50, 1.0),
            wait_for_button(),

            #calibrate_wait_for_light(Defs.wait_for_light_sensor),
        ])
