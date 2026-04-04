from libstp import *

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
            drive_forward(cm=40),
            line_follower().distance_cm(150),

            #let botguy go
            Defs.claw_servo.open(),
            Defs.cone_arm_servo._90deg(),
        ])