from libstp import *

from src.hardware.defs import Defs
from src.steps.follow_line_single2_step import follow_line_single2
from src.steps.drum_collector import drum_retreat


class M1000TestMission(Mission):
   def sequence(self) -> Sequential:
       return seq([
           turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),
           turn_left(180, 1),
           turn_right(180, 1),
           turn_left(90, 1),
           turn_right(90, 1),

           WaitForButton(),
           turn_left(180, 1),
           turn_right(180, 1),
           turn_left(90, 1),
           turn_right(90, 1),

           WaitForButton(),
           turn_left(180, 1),
           turn_right(180, 1),
           turn_left(90, 1),
           turn_right(90, 1),

           WaitForButton(),turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),turn_left(180,1),
           turn_right(180,1),
           turn_left(90,1),
           turn_right(90,1),

           WaitForButton(),
       ])
