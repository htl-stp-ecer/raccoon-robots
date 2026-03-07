from libstp import *
from src.steps.drum_collector import drum_retreat
from src.steps.drum_lifting_step import drum_lifting_up, dispense_drums


class M03DriveToPipe(Mission):
   def sequence(self) -> Sequential:
       return seq([
           dispense_drums(),
           drive_backward(35,1),
           turn_right(90,1),
           drive_backward(15,1),
           drive_forward(11,1),
           turn_right(90,1),
           drive_forward(43,1),

           drum_retreat(),
           drum_retreat(),
           drum_retreat(),
           drum_retreat(),
           drum_retreat(),
           drum_retreat(),
           drum_retreat(),
           drum_retreat(),
           drum_retreat(),



       ])






