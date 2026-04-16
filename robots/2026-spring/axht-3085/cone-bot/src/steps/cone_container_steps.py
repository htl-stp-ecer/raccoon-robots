from raccoon import *

from src.hardware.defs import Defs

def down_cone_container():
    return seq([
        set_motor_velocity(Defs.cone_container_motor, velocity=-1700),
        wait_for_seconds(0.3),
        motor_passive_brake(Defs.cone_container_motor),
        drive_forward(cm=10),
        set_motor_velocity(Defs.cone_container_motor, velocity=1700),
        wait_for_seconds(0.1),
        motor_passive_brake(Defs.cone_container_motor),
    ])
