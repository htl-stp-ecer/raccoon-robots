from raccoon import *

from src.hardware.defs import Defs

def line_follower():
    return follow_line_single(
        sensor=Defs.front_right_ir_sensor,
        speed=1.0,
        side=LineSide.RIGHT,
    )


class M050DriveToStartingBoxMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("upper"),
            #drive up tehe ramp and in front of the startingbox
            drive_backward(cm=30),
            turn_to_heading_right(180),
            drive_backward(cm=200, heading=180),
        ])