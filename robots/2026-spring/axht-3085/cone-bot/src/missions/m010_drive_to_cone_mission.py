from libstp import *

from src.hardware.defs import Defs


class M010DriveToConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #align on pipe
            Defs.cone_arm_servo._45deg(),
            drive_backward(cm=3),
            turn_right(55),
            wall_align_backward(
                speed=0.5,
                accel_threshold=0.3,
            ),
            mark_heading_reference(),

            #push the sorted pom
            drive_forward(cm=2),
            Defs.cone_arm_servo.down(),
            turn_left(25),

            #grab orange maching pom
            Defs.cone_arm_servo.container_pos(),
            parallel(
                Defs.claw_servo.open(),
                turn_to_heading_right(25),
            ),
            Defs.cone_arm_servo.down(),
            Defs.claw_servo.closed(),

            #drive in the middle of the poms
            parallel(
                turn_to_heading_right(0),
                Defs.cone_arm_servo._45deg(),
            ),
            drive_forward().until(
              on_black(Defs.front_right_ir_sensor) >
              after_cm(25),
            ),

            #drive to position where we dorp the pom
            turn_to_heading_right(90),
            drive_forward(cm=35),

            #drop pom
            parallel(
                turn_right(35),
            ),
            Defs.claw_servo.open(),
            Defs.claw_servo.closed(),

            #drive to cone
            turn_to_heading_right(90),
            Defs.front.drive_until_black(),
        ])
