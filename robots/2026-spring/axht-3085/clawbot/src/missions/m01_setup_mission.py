from libstp import *

from src.hardware.defs import Defs


class M01SetupMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            parallel(
                Defs.pom_arm.start(),
                Defs.pom_grab.start(),
                Defs.shild.down(),
                Defs.shild_graber.closed(),
            ),
            stop(),
            wait_for_seconds(1),
            stop(),

            calibrate(distance_cm=50,
                      calibration_sets=["default", "upper"],
                      ),

            switch_calibration_set("upper"),
        ])
