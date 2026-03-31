from libstp import servo

from src.hardware.defs import Defs


def open_drum_pusher():
    return servo(Defs.drum_pusher_servo, 140)

def use_drum_to_block():
    return servo(Defs.drum_pusher_servo, 40)

def close_drum_pusher():
    return servo(Defs.drum_pusher_servo, 0)