from libstp import *

from src.hardware.defs import Defs


class M100DriveAwayMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #get straight
            turn_to_heading_right(0),

            strafe_right().until(on_black(Defs.rear.right) | after_seconds(2)),

            #wait until the other bot is gone
            wait_for_checkpoint(110),
            turn_right(20),
            turn_to_heading_left(0),
        ])
