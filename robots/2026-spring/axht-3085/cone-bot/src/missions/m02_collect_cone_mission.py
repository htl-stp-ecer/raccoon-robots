from libstp import *

from src.hardware.defs import Defs


class M02CollectConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_backward(10),
            turn_left(30),
            drive_backward(5),
            Defs.claw_servo.open(),
            Defs.cone_arm_servo.down(),
            Defs.claw_servo.closed(60),
            Defs.cone_arm_servo.up(60),
            Defs.claw_servo.open(),
            drive_forward(5),
            turn_right(30),
            Defs.front.drive_until_black(),
        ])