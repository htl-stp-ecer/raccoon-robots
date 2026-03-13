from libstp import *

from src.steps.drum_collector import drum_retreat


class M1000TestMission(Mission):
   def sequence(self) -> Sequential:
       return seq([
           wait_for_checkpoint(checkpoint_timestamp + time_before_collecting_drum),
           close_drum_pusher(),
           drum_retreat(),
           # relative soon
           set_motor_velocity(Defs.drum_motor, -830),
           wait_for_seconds(0.3),
           motor_passive_brake(Defs.drum_motor),

           WaitForButton(),
           drum_retreat(),
           WaitForButton(),
           drum_retreat(),
           WaitForButton(),
           drum_retreat(),

           WaitForButton(),
           drum_retreat(),
           WaitForButton(),
           drum_retreat(),
           WaitForButton(),
           drum_retreat(),
           WaitForButton(),
           drum_retreat()
       ])