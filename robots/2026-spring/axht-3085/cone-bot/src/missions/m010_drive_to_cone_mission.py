from libstp import *

from src.hardware.defs import Defs


class M010DriveToConeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #magical stuff so we don't hit the T pice of the pipe
            parallel(
                seq([
                    turn_left(5),
                    drive_backward(3),
                ]),
                Defs.cone_arm_servo._45deg(),
            ),

            #align on pipe
            turn_right(65),
            wall_align_backward(
                speed=0.3,
                accel_threshold=0.3,
                settle_duration=0,
            ),
            mark_heading_reference(origin_offset_deg=0),

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

            #align the second time on the pipe
            wall_align_backward(
                speed=0.3,
                accel_threshold=0.3,
                settle_duration=0,
            ),
            mark_heading_reference(origin_offset_deg=0),

            #drive over black line
            drive_forward().until(
              on_black(Defs.front_right_ir_sensor) >
              after_cm(25)
            ),

            #drive to position where we dorp the pom
            turn_to_heading_right(90),
            drive_forward(cm=35),

            #drop pom
            parallel(
                turn_left(40),
            ),
            Defs.claw_servo.open(),
            Defs.claw_servo.closed(),

            #drive to cone
            turn_to_heading_right(90),
            Defs.front.drive_until_black(),
        ])
