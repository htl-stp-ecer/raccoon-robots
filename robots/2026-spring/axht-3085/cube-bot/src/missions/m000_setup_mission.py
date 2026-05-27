from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs

class M000SetupMission(SetupMission):
    setup_time = 120

    def sequence(self) -> Sequential:
        return seq([
            pause_setup_timer(),
            fully_disable_servos(),

            wait_for_button("move servos into starting position"),
            start_setup_timer(),

            # arm start position
            Defs.arm_claw.idle(),
            arm.move_angles(0, 110, -120),

            fully_disable_servos(),

            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
            ),
        ])
