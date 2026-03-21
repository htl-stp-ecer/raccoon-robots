from libstp import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import dispense_drums
from src.steps.follow_line_single2_step import follow_line_single2
from src.steps.drum_collector import drum_retreat
from src.steps.range_finder import turn_to_peak


class M1000TestMission(Mission):
   def sequence(self) -> Sequential:
       return seq([
           #turn_to_peak(turn_speed = 0.2),
           #parallel(turn_left(22, 1), dispense_drums()),
           #wall_align_forward(speed=0.3, accel_threshold=0.25, settle_duration=0, max_duration=3, grace_period=0.4),
            turn_left(90,1),
           wait_for_button(),
           turn_right(90,1),
           wait_for_button(),

           turn_left(90, 1),
           wait_for_button(),
           turn_right(90, 1),
           wait_for_button(),
           turn_left(90, 1),
           wait_for_button(),
           turn_right(90, 1),
           wait_for_button(),
           turn_left(90, 1),
           wait_for_button(),
           turn_right(90, 1),
           wait_for_button(),
           turn_left(90, 1),
           wait_for_button(),
           turn_right(90, 1),
           wait_for_button(),

       ])
