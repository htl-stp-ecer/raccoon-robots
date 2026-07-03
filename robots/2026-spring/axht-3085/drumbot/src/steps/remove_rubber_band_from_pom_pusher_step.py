from raccoon import *
from src.hardware.defs import Defs

def remove_rubber_band_from_pom_pusher():
    return seq([
        Defs.pom_remover_servo.left(),
        Defs.pom_remover_servo.drum_moving_pos(),
    ])
