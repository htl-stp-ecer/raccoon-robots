from src.hardware.defs import Defs
from libstp import Mission, Sequential, seq, drive_forward, follow_line

from src.steps.single_line_follow import follow_line_single, LineSide


class TestMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            follow_line_single(Defs.front_right_light_sensor, 40, 1.0),
            #strafe_left_lineup_on_black(Defs.front_left_light_sensor, Defs.rear_left_light_sensor, 0.9),
            #strafe_right_until_black([Defs.front_left_light_sensor, Defs.rear_left_light_sensor], 1.0),

            #simpl_frontside_forward_lineup_on_black(),
            #drive_forward_until_black([Defs.front_left_light_sensor, Defs.front_right_light_sensor]),
            #wait(10),
            #drive_forward(10, 1.0),
            #drive_backward_until_black([Defs.front_left_light_sensor, Defs.front_right_light_sensor]),

            #frontside_forward_lineup_on_black(),

            #drive_forward(20,0.1),
        ])
