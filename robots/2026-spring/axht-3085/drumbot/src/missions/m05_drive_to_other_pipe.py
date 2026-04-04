from libstp import *

from src.hardware.defs import Defs
from src.missions.m04_eject_drums_mission import eject_nearest_color
from src.steps.drum_lifting_step import *
from src.steps.range_finder import turn_to_peak
from src.steps.drive_to_pipe import drive_to_second_pipe


class M05DriveToOtherPipe(Mission):
    def sequence(self) -> Sequential:
        return seq([

            parallel(drive_backward(7, 1), drum_lifting_up()),
            turn_left(20, 1),
            drive_backward(40, 1),
            drive_backward().until(on_black(Defs.front_right_ir_sensor)),
            drive_forward(2.5, 1),
            turn_left().until(on_black(Defs.front_right_ir_sensor)),
            follow_line_single(Defs.front_right_ir_sensor, kp=0.3, kd=0.1, side=LineSide.RIGHT).until(
                on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor)),
            drive_forward(12, 1),

            drive_to_second_pipe(),
            drum_seek(),
            turn_to_peak(turn_speed=0.4, profile="first_pipe"),
            turn_left(3.5, 1),

            drive_to_analog_target(Defs.et_range_finder),
            #turn_left(19.5, 1),

            parallel(
                drive_backward(2.5, 1),
                drum_eject_position(),
            ),

            wait_for_button(),
            eject_nearest_color(),

        ])
