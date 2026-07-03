from raccoon import *
from src.hardware.defs import Defs

def pom_pusher_rubber_band_avoid_pos():
    # meant for driving around when the rubber bands could catch on the pom pusher
    return background(
        Defs.pom_remover_servo.right(),
    )

def pom_pusher_obstacle_avoid_pos():
    # meant for ejecting when the pom pusher could potentially be sandwiched between an object and the robot
    return background(
        Defs.pom_remover_servo.drum_moving_pos(),
    )
