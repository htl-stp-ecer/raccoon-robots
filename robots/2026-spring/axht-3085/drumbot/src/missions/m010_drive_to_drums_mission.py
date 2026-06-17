from raccoon import *
from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),

            # drive out of starting box
            drive_forward(heading=0).until(
                over_line(Defs.front_right_ir_sensor)
            ),

            # turn drive turn
            turn_right(45),
            drive_forward().until(
                over_line(Defs.rear_left_ir_sensor)
                + after_cm(4),
            ),
            background(
                Defs.pom_remover_servo.right()
            ),
            turn_to_heading_right(0),

            # wait a little and then remove the blue pom
            background(
                seq([
                    Defs.pom_remover_servo.yeet_blue_pom(),
                    Defs.pom_remover_servo.drum_moving_pos(),
                ]),
            ),

            drive_forward(heading=0).until(
                over_line(Defs.front_right_ir_sensor)
                + after_cm(15)
            ),
            turn_to_heading_left(0),

            background(
                parallel(
                    Defs.lift_drums_servo.down(),
                    Defs.drum_pusher_servo.open(),
                ),
                name="lower_drum",
            ),

            wall_align_forward(
                accel_threshold=0.3,
                grace_period=0.2,
            ),
            mark_heading_reference(),
        ])
