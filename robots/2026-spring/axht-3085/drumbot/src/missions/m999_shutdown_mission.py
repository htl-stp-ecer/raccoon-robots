from raccoon import *
from src.hardware.defs import Defs
from src.steps.camera_lifecycle_step import stop_camera

class M999ShutdownMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                stop_camera(),
                fully_disable_servos(),
                motor_off(Defs.cone_pusher_motor)
            ),
        ])
