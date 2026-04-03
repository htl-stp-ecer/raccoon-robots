from libstp import *

from src.hardware.defs import Defs


class M027DriveToBotguyMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #drive back in front of dores
            parallel(
                drive_backward().until(
                    on_black(Defs.front_right_ir_sensor) >
                    on_white(Defs.front_right_ir_sensor)
                ),
                Defs.claw_servo.closed(120),
            ),

            #turn to dors
            turn_to_heading_right(0),

            drive_forward().until(
                on_black(Defs.front_right_ir_sensor)
            ),
        ])