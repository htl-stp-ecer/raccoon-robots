from libstp import *

from src.hardware.defs import Defs


class M01SetupMission(Mission):
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
            stop(),
            wait_for_seconds(1),

            #auto_tune(
            #    vel_axes=["vy"],
            #    tune_motion=False,
            #    characterize_axes=["lateral"]
            #),
            calibrate(distance_cm=70,
                      calibration_sets=["default", "upper"],
                      ),

        ])
