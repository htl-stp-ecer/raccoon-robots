from libstp import *

from src.hardware.defs import Defs
from src.steps.et_scan_align import EtScanAlign


class M000SetupMission(SetupMission):
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


            #timeout_or(drive_forward().until(after_seconds(3)),
            #           seconds=1,
            #           fallback=drive_backward(cm=5),
            #           ),

            #auto_tune(
            #    vel_axes=["vy"],
            #    tune_motion=False,
            #    characterize_axes=["lateral"]
            #),
            calibrate(distance_cm=70,
                      calibration_sets=["default", "upper"],
                      ),

        ])
