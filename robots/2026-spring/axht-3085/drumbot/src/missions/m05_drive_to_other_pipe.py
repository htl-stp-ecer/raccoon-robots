from libstp import *

from src.hardware.defs import Defs
from src.missions.m04_reject_drums_mission import reject_drums
from src.steps.drum_lifting_step import *


class M05DriveToOtherPipe(Mission):
    def sequence(self) -> Sequential:
            return seq([

                drive_backward(30,1),
                turn_right(20,1),
                drive_backward(30,1),

                turn_left(110,1),
                follow_line(Defs.front_left_ir_sensor,Defs.front_right_ir_sensor,speed = 1).until(on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor)),
                follow_line(Defs.front_left_ir_sensor, Defs.front_right_ir_sensor, speed=1).until(on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor)),

                wall_align_forward(speed=0.3, accel_threshold=0.25, settle_duration=0, max_duration=3, grace_period=0.4),

                reject_drums(),
                reject_drums(),
                shake_drums(),
                dispense_drums(),
                reject_drums(),
                reject_drums(),
                reject_drums(),
            ])
