from raccoon import *
from src.hardware.defs import Defs
from src.steps.camera_lifecycle_step import stop_camera

class M999ShutdownMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                turn_left(45),
                seq([
                    wait_for_seconds(0.2),
                    Defs.lift_drums_servo.seek_position(120),
                ]),
            ),
            stop_camera(),
        ])
