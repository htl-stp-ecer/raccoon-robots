from raccoon import *
from src.hardware.defs import Defs

def remove_rubber_band_from_pom_pusher():
    return loop_for(
        seq([
            Defs.pom_remover_servo.left(),
            Defs.pom_remover_servo.drum_moving_pos(),
        ]),
        iterations=2
    )
