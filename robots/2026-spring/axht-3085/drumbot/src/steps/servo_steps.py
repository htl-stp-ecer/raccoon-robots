from libstp import servo, slow_servo

from src.hardware.defs import Defs


def open_drum_pusher():
    return servo(Defs.drum_pusher_servo, 140)

def use_drum_to_block():
    return servo(Defs.drum_pusher_servo, 66)

def close_drum_pusher():
    return servo(Defs.drum_pusher_servo, 0)


def push_orange_pom_away():
    return servo(Defs.pom_remover_servo, 170)

def Pom_puher_Start():
    return servo(Defs.pom_remover_servo, 60)
def Pom_pusher_oben():
    return servo(Defs.pom_remover_servo, 30)



