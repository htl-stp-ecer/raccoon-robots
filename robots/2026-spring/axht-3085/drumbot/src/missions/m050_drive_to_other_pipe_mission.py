from libstp import *

from src.hardware.defs import Defs
from src.missions.m040_eject_drums_mission import eject_nearest_color
from src.steps.drum_lifting_step import *
from src.steps.range_finder import turn_to_peak
from src.steps.drive_to_pipe import drive_to_second_pipe


class M050DriveToOtherPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([

            parallel(drive_backward(7, 1), drum_lifting_up()),
            turn_left(15, 1),
            drive_backward().until(
                after_cm(40) >
                on_black(Defs.front_right_ir_sensor)

            ),
            #drive_backward(40, 1),
            #drive_backward().until(on_black(Defs.front_right_ir_sensor)),
            drive_forward(2.5, 1),
            turn_left().until(on_black(Defs.front_right_ir_sensor)),

            follow_line_single(Defs.front_right_ir_sensor, kp=1, kd=0.1, side=LineSide.RIGHT, speed=1.0).until(
                on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor) >
                after_cm(12)

            ),




          #  follow_line_single(Defs.front_right_ir_sensor, kp=0.3, kd=0.1, side=LineSide.RIGHT).until(
            #    on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor)),
           # drive_forward(12, 1),



            drive_to_second_pipe(),
            drum_seek(),
            turn_to_peak(turn_speed=0.4, profile="first_pipe"),
            turn_left(5, 1),

            #drive_to_analog_target(Defs.et_range_finder),
            #turn_left(19.5, 1),

            wall_align_forward(speed=0.7, accel_threshold=0.3, settle_duration=0.2, max_duration=3, grace_period=0.4),
            parallel(
                drive_backward(3.3, 1),
                drum_eject_position()
            ),

            eject_nearest_color()
        ])
