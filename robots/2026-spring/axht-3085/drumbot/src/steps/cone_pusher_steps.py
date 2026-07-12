from raccoon import *
from src.hardware.defs import Defs

MOTOR_VELOCITY = 1300
DOWN_POSITION = -420

@dsl()
def lower_cone_pusher():
    return seq([
        move_motor_relative(Defs.cone_pusher_motor, DOWN_POSITION, MOTOR_VELOCITY),
        motor_brake(Defs.cone_pusher_motor),
    ])
