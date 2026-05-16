from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.line_follow_dsl import lateral_follow_line_single


class M000SetupMission(SetupMission):
    def sequence(self) -> Sequential:
        setup_time = 120

        return seq([
            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
            ),
            lateral_follow_line_single(
                sensor=Defs.rear.left,
                distance_cm=100,
                speed=1,
                side=LineSide.RIGHT,
                kp=0.4,
                ki=0.1,
                kd=0.0,
            ),

            pause_setup_timer(),
            fully_disable_servos(),

            wait_for_button("move servos into starting position"),
            start_setup_timer(),  # countdown begins here, full duration

            # arm start position
            Defs.arm_claw.closed(),
            arm.move_angles(0, 90, 0),
            arm.move_angles(-80, 100, 90),

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
        ])
