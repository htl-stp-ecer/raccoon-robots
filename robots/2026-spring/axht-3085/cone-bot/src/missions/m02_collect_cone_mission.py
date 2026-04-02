from libstp import *

from src.hardware.defs import Defs


class M02CollectConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_backward(10),
            turn_left(25),
            drive_backward(6),
            Defs.claw_servo.open(),
            Defs.cone_arm_servo.down(),
            Defs.claw_servo.closed(120),
            Defs.cone_arm_servo.up(140),
            Defs.claw_servo.half_open(100),
            drive_forward(9),
            turn_right(25),
            Defs.front.drive_over_line(),
        ])