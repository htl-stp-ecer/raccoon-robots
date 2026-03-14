from libstp import *

from src.hardware.defs import Defs
from src.missions.m04_reject_drums_mission import reject_drums
from src.steps.follow_line_single2_step import follow_line_single2
from src.steps.drum_lifting_step import *
from src.steps.range_finder import turn_to_peak


class M05DriveToOtherPipe(Mission):
    def sequence(self) -> Sequential:
            return seq([

                drive_backward(65,1),
                turn_left(110,1),
                follow_line_single(Defs.front_right_ir_sensor).until(on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor)),
                drive_forward(10,1),
                follow_line_single(Defs.front_right_ir_sensor).until(on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor)),
                follow_line_single(Defs.front_right_ir_sensor, 42),

                turn_to_peak(),
                parallel(turn_left(22, 1), dispense_drums()),

                wall_align_forward(speed=0.3, accel_threshold=0.35, settle_duration=0, max_duration=3, grace_period=0.4),
                drive_backward(2.5,1),

                reject_drums(),
                reject_drums(),
                #shake_drums(),
                #dispense_drums(),
                reject_drums(),
                reject_drums(),
                reject_drums(),


            ])
