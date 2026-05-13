from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs


class M000SetupMission(SetupMission):
    def sequence(self) -> Sequential:
        setup_time = 120
        return seq([
            loop_forever(
                seq([  # TODO: mehr hinten beim loslassen
                    wait_for_button("init"),
                    arm.move_angles(-90, 40, -30),

                    wait_for_button("go"),
                    arm.move_angles(-90, 90, -100),
                    # wait_for_button(),
                    arm.move_angles(-90, 90, -50),
                    # wait_for_button(),
                    # arm.move_angles(0, 90, -50, speed=100),
                    arm.move_angles(105, 90, -50, speed=100),
                    # wait_for_button(),
                    arm.move_angles(105, 90, -100, speed=60),
                    # wait_for_button(),
                    arm.move_angles(140, 90, -100, speed=70),

                    # wait_for_button(),
                    arm.move_angles(110, 90, -100),
                    # wait_for_button(),
                    arm.move_angles(110, 90, 0),
                    arm.move_angles(0, 90, 0),

                    wait_for_button("press to disable servos fully"),
                    fully_disable_servos(),
                ]),
            ),

            pause_setup_timer(),
            fully_disable_servos(),

            wait_for_button("move servos into starting position"),
            start_setup_timer(),  # countdown begins here, full duration

            # arm start position
            parallel(
                arm.move_angles(-55, 90, 90),
                Defs.arm_claw.closed(),
            ),
            fully_disable_servos(),

            # auto_tune(
            #    vel_axes=["vy"],
            #    tune_motion=False,
            #    characterize_axes=["lateral"]
            # ),
            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
            ),

            fully_disable_servos(),
        ])
