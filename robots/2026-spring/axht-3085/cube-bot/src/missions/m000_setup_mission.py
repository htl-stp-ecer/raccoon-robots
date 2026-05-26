from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs


def test():
    return seq([
        wait_for_button("go"),

        arm.move_angles(-90, 80, -75),
        Defs.arm_claw.full_open(),
        arm.move_angles(-120, 80, -75),
        arm.move_angles(-90, 80, -75),
        Defs.arm_claw.open(),
        arm.move_angles(-90, 40, -50),
        wait_for_button(),
        arm.move_angles(-90, 25, -25),
        wait_for_button(),
        Defs.arm_claw.grab(),

        wait_for_button("fully disable"),
        fully_disable_servos(),
    ])


class M000SetupMission(SetupMission):
    def sequence(self) -> Sequential:
        setup_time = 120

        return seq([
            # loop_forever(
            #     test()
            # ),

            pause_setup_timer(),
            fully_disable_servos(),

            wait_for_button("move servos into starting position"),
            start_setup_timer(),

            # arm start position
            Defs.arm_claw.idle(),
            arm.move_angles(-90, 110, -120),

            fully_disable_servos(),

            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
            ),
        ])
