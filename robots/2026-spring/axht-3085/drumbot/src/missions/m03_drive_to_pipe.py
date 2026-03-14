from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_up, dispense_drums, shake_drums
from src.steps.range_finder import turn_to_peak
from src.steps.range_finder.scan_sweep_step import ScanSweepStep


class M03DriveToPipe(Mission):
   def sequence(self) -> Sequential:
       return seq([
           drum_lifting_up(),
           drive_backward(25,1),
           turn_right(180,1),
           forward_lineup_on_black(Defs.front_left_ir_sensor, Defs.front_right_ir_sensor),
           drive_forward(26,1),

           turn_to_peak(),
           parallel(turn_left(22,1),dispense_drums()),

           wall_align_forward(speed=0.3, accel_threshold=0.25, settle_duration=0, max_duration=3, grace_period=0.4),
           parallel(drive_backward(2.5,1),shake_drums()),

       ])






