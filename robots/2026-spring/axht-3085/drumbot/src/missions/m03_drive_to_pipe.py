from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_up, shake_drums
from src.steps.range_finder import turn_to_peak


class M03DriveToPipe(Mission):
   def sequence(self) -> Sequential:
       return seq([
           drum_retreat(),
           drum_lifting_up(),
           drive_backward(35,1),
           turn_right(180,1),
           drive_forward().until(on_white(Defs.front_right_ir_sensor)),
           drive_forward(23,1),

           turn_to_peak(turn_speed = 0.4),
           turn_left(19,1),

           wall_align_forward(speed=0.3, accel_threshold=0.25, settle_duration=0, max_duration=3, grace_period=0.4),
           parallel(drive_backward(2.5,1),shake_drums()),

       ])






