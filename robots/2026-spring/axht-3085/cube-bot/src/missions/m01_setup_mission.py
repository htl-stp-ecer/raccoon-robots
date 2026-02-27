from libstp import *
from src.hardware.defs import *
from src.steps.light_sensor_steps import frontside_forward_lineup_on_black, frontside_line_follow_right_edge
from src.steps.servo_steps import *


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
            follow_line_single(
                Defs.front_right_light_sensor,
                70,
                1.0,
                LineSide.RIGHT,
                2,
                0.001,
                0.0,
            ),
            wait_for_button(),

            #calibrate_wait_for_light(Defs.wait_for_light_sensor),
        ])
