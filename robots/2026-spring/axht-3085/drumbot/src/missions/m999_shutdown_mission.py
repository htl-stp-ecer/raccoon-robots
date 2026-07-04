from raccoon import *
from src.hardware.defs import Defs
from src.steps.camera_lifecycle_step import stop_camera

class M999ShutdownMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            stop_camera(),
        ])
