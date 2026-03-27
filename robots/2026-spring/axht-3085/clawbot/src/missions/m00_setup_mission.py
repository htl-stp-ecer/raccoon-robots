from libstp import *

from src.hardware.defs import Defs

def line_follow_backward(speed=1.0):
    return strafe_follow_line_single(
        Defs.front.left,
        speed=-speed,
        side=LineSide.RIGHT,
        kp=0.5,
        kd=0.1,
    )

class M00SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                Defs.shild.down(),
                Defs.shild_graber.closed(),
            ),

            parallel(
                Defs.pom_arm.start(100),
                Defs.pom_grab.start(100),
            ),

            Defs.shild.up(),


            #auto_tune(
            #    vel_axes=["vy"],
            #    tune_motion=False,
            #    characterize_axes=["lateral"]
            #),
            calibrate(distance_cm=70,
                      calibration_sets=["default", "upper"],
                      ),
        ])
