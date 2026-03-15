from libstp import *

from src.hardware.defs import Defs
from src.steps.follow_line_single2_step import follow_line_single2
from src.steps.drum_collector import drum_retreat


class M1000TestMission(Mission):
   def sequence(self) -> Sequential:
       return seq([
           drive_forward().until(on_white(Defs.front_left_ir_sensor) & on_white(Defs.front_right_ir_sensor)),
       ])
