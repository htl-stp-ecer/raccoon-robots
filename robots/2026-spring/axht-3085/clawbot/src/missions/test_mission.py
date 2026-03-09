from libstp import strafe_left_lineup_on_black, strafe_right_until_black, forward_lineup_on_black, drive_until_black, \
    drive_forward_until_black, follow_line_single
from libstp.mission.api import Mission
from libstp.step.sequential import Sequential, seq
from libstp import *
from src.hardware.defs import Defs


class TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #strafe_right_until_black([Defs.front_left_light_sensor, Defs.rear_left_light_sensor], 1.0),

            #simpl_frontside_forward_lineup_on_black(),
            #drive_forward_until_black([Defs.front_left_light_sensor, Defs.front_right_light_sensor]),
            #wait(10),
            #drive_forward(10, 1.0),
            #drive_backward_until_black([Defs.front_left_light_sensor, Defs.front_right_light_sensor]),

            #frontside_forward_lineup_on_black(),

            #drive_forward(20,0.1),
        ])
