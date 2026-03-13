from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_up, dispense_drums
from src.steps.range_finder import turn_to_peak
from src.steps.range_finder.scan_sweep_step import ScanSweepStep


class M03DriveToPipe(Mission):
   def sequence(self) -> Sequential:
       return seq([
           dispense_drums(),
           drive_backward(25,1),
           turn_right(180,1),
           forward_lineup_on_black(Defs.front_left_ir_sensor, Defs.front_right_ir_sensor),
           drive_forward(26,1),

           turn_to_peak(),
           turn_left(20,1),
           drive_forward(6,1),


           drum_retreat(),
           drum_retreat(),
           drum_retreat(),
           drum_retreat(),

       ])






