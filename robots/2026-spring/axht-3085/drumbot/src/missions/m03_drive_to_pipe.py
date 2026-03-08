from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_up, dispense_drums
from src.steps.range_finder.scan_sweep_step import ScanSweepStep


class M03DriveToPipe(Mission):
   def sequence(self) -> Sequential:
       return seq([
           dispense_drums(),
           drive_backward(30,1),
           turn_right(180,1),
           forward_lineup_on_black(Defs.front_left_ir_sensor, Defs.front_right_ir_sensor),
           drive_forward(27.5,1),

           ScanSweepStep(),
           turn_left(15,1),
           drive_forward(8,1),



           drum_retreat(),
           drum_retreat(),
           drum_retreat(),
           drum_retreat(),



       ])






