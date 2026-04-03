from libstp import *
from pydantic.json_schema import DefsRef

from src.hardware.defs import Defs


class M030CollectBotguyMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #push big cube
            Defs.cone_arm_servo._20deg(),
            turn_right().until(
                after_degrees(45) | after_seconds(1.0),
            ),

            #turn back to dors and make arm ready
            parallel(
                turn_to_heading_right(20), #turn 20 inital deg
                Defs.cone_arm_servo._20deg(),
            ),

            #open left dor
            drive_forward(cm=7),
            turn_left().until(
                after_degrees(50) | after_seconds(1.0) #turn 30 deg + 20 deg inital
            ),

            #turn back to botguy
            #turn_to_heading_right(0),

            #open right dor
            turn_right().until(
                after_degrees(50) | after_seconds(1.0)
            ),

            #grab botguy
            Defs.cone_arm_servo.container_pos(),
            turn_to_heading_right(0),
            drive_backward(cm=10),
            #parallel(
            #    turn_to_heading_right(30),
            #    Defs.claw_servo.half_open(),
            #    Defs.cone_arm_servo._45deg(),
            #),
            #drive_forward(cm=15),
            #Defs.claw_servo.closed(),

        ])