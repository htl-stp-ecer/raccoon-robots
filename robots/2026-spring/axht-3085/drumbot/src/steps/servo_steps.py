from libstp import servo

from src.hardware.defs import Defs


def open_drum_pusher():
    return servo(Defs.drum_pusher_servo, 170)

def use_drum_to_block():
    return servo(Defs.drum_pusher_servo, 70)

def close_drum_pusher():
    return servo(Defs.drum_pusher_servo, 30)


def driving_position_pom_remover_servo():
    return servo(Defs.pom_remover_servo,170)

def swap_pom_remover_servo():
    return servo(Defs.pom_remover_servo, 0)