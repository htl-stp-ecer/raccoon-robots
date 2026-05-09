from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.et_scan_align import EtScanAlign


class M000SetupMission(SetupMission):
    def sequence(self) -> Sequential:
        setup_time = 120
        return seq([
            pause_setup_timer(),
            fully_disable_servos(),
            wait_for_button("move servos into starting position"),
            start_setup_timer(),  # countdown begins here, full duration

            #arm start position
            arm.move_angles(0, 90, 90),
            Defs.arm_claw.closed(),


            #auto_tune(
            #    vel_axes=["vy"],
            #    tune_motion=False,
            #    characterize_axes=["lateral"]
            #),
            calibrate(distance_cm=70,
                      calibration_sets=["default", "upper"],
                      ),

            fully_disable_servos(),
        ])
