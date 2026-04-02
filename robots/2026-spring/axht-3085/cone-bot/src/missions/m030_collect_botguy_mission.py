from libstp import *
from pydantic.json_schema import DefsRef

from src.hardware.defs import Defs


class M030CollectBotguyMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #push big cube
            Defs.cone_arm_servo._20deg(),
            turn_right().until(
                after_degrees(45) | after_seconds(1.5),
            ),

            #turn back to dors and make arm ready
            parallel(
                turn_to_heading_right(10),
                Defs.cone_arm_servo._45deg(),
            ),

            #open left dor
            drive_forward().until(
                on_white(Defs.front_right_ir_sensor) >
                after_cm(cm=5)
            ),
            turn_left().until(
                after_degrees(45) | after_seconds(1.5),
            ),

            #turn back to botguy
            turn_to_heading_right(0),

            #open right dor
            drive_forward(5),

            turn_right().until(
                after_degrees(45) | after_seconds(1.5),
            ),
        ])