from libstp import *
from pydantic.json_schema import DefsRef

from src.hardware.defs import Defs


class M03CollectBotguyMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
        mark_heading_reference(),
        turn_left(120),
        Defs.claw_servo.closed(),
        Defs.cone_arm_servo.slight_up(),
        turn_right(60),
        Defs.cone_arm_servo.up(),
        turn_left(30),
        Defs.cone_arm_servo.more_slight_up(),
        drive_forward(15),
        turn_right(15),
        turn_left(30),
        turn_right(30),
        turn_left(15),
        Defs.claw_servo.half_open(),
        turn_right(5),
        drive_forward(10),
        Defs.cone_arm_servo.down(),
        wait_for_seconds(1),
        Defs.claw_servo.closed(),
        Defs.cone_arm_servo.more_slight_up(),
        drive_backward(20),
        Defs.cone_arm_servo.up(),
        turn_right(85),
        Defs.front.drive_until_black(),
        drive_forward(30),
        turn_right(90),
        ])