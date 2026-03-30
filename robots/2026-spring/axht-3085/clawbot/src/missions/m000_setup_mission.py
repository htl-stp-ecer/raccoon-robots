from libstp import *

from src.hardware.defs import Defs
from src.steps.et_scan_align import EtScanAlign


class M000SetupMission(Mission):
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

            wait_for_button(),
            EtScanAlign(
                50,
                "right",
                0.7,
                0,
                Defs.distance_sensor
            ),

            #auto_tune(
            #    vel_axes=["vy"],
            #    tune_motion=False,
            #    characterize_axes=["lateral"]
            #),
            calibrate(distance_cm=70,
                      calibration_sets=["default", "upper"],
                      ),

        ])
