from libstp import *

from src.hardware.defs import Defs


class M100DriveAwayMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #get straight
            turn_to_heading_right(0),

            strafe_right().until(on_black(Defs.rear.right)),
        ])
