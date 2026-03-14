from libstp import *

from src.hardware.defs import Defs


class M01DriveToConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            Defs.cone_arm_servo.up(),
            drive_backward(7),
            turn_right(55),
            wall_align_backward(accel_threshold=0.3),
            drive_forward(2),
            Defs.cone_arm_servo.down(),
            turn_left(25),
            turn_right(25),
            Defs.cone_arm_servo.up(),
            Defs.front.drive_until_black(),
            # forward_single_lineup(
            #     Defs.front.right,
            #     correction_side=CorrectionSide.RIGHT,
            # ),
            drive_forward(27),
            turn_right(90),
            Defs.front.drive_until_black(),
        ])
