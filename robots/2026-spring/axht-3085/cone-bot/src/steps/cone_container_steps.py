from libstp import *

from src.hardware.defs import Defs

def down_cone_container():
    return seq([
        set_motor_velocity(Defs.cone_container_motor, -100),
        wait_for_digital(Defs.cone_arm_down_button),
        motor_passive_brake(Defs.cone_container_motor)
    ])
