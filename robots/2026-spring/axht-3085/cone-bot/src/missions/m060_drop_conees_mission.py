from raccoon import *

from src.hardware.defs import Defs
from src.steps.cone_container_steps import down_cone_container


class M060DropConeesMission(Mission):
    def sequence(self) -> Sequential:
        return seq([

            # make sure we are straight
            turn_to_heading_right(0),

            # position to drop cones
            drive_backward(cm=5),

            #drop cones
            turn_to_heading_right(135),
            down_cone_container(),

            #drive away from starting box
            drive_forward(cm=10),


            #turn back so we face and dirve into starting box
            turn_to_heading_right(0),
            drive_forward(cm=35),
        ])
