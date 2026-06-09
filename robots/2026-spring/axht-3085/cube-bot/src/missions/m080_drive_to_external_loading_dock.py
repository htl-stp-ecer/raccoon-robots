from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.calibrate_analog_drive import on_analog_flank
from src.steps.line_follow_dsl import lateral_follow_line_single, lateral_follow_line_single_free

def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.5,
        ki=0.3,
        kd=0.0,
    )


class M080DriveToExternalLoadingDock(Mission):
    def sequence(self) -> Sequential:
        return seq([

            line_follow().until(
                after_cm(100)
                + over_line(Defs.rear.left)
                + after_cm(5)
            ),
            switch_calibration_set("default"),
            strafe_right().until(
                over_line(Defs.front.right)
                + over_line(Defs.front.right)
                + over_line(Defs.rear.left)
            ),

        ])