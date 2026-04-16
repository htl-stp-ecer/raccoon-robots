from raccoon import *
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
            drive_forward(cm=9), #hardcodes magic value to controll how hard we push into the dor
            turn_left().until(
                after_degrees(50) | after_seconds(1.0) #turn 30 deg + 20 deg inital
            ),

            #turn back to botguy
            #turn_to_heading_right(0),

            #open right dor
            turn_right().until(
                after_degrees(50) | after_seconds(1.0)
            ),

            #align on botguy
            Defs.cone_arm_servo.container_pos(),
            turn_to_heading_right(0),
            drive_backward().until(
                on_black(Defs.front_right_ir_sensor) >
                after_cm(5),
            ),

            #grab botguy
            parallel(
                turn_to_heading_right(14),
                Defs.claw_servo.botguy_open(),
                Defs.cone_arm_servo.botguy_head_hight(),
            ),
            drive_forward(cm=24),

            #move botguy out
            Defs.claw_servo.botguy_closed(),
            Defs.cone_arm_servo._45deg(),
            turn_to_heading_left(0),
            drive_backward(cm=25),

            #align on black line
            turn_to_heading_left(0),
        ])