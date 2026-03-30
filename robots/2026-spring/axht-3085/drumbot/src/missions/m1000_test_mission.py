from libstp import *

from src.steps.drum_collector import calibrate_sort_into_slot


class M1000TestMission(Mission):
   def sequence(self) -> Sequential:
       return seq([
           calibrate_sort_into_slot(pocket_count=1),
       ])
