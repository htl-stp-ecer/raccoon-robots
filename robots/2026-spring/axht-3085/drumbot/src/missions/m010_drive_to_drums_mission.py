from raccoon import *
from src.hardware.defs import *
from src.steps.drum_lifting_step import *

class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(origin_offset_deg=-90),

            background(
                Defs.lift_drums_servo.up(),
            ),

            wait_for_seconds(0.3),

            drive_backward(heading=90).until(
                on_black(Defs.rear_left_ir_sensor)
            ),

            turn_right(45),
            drive_forward(14),
            parallel(
                turn_to_heading_left(0),
                Defs.pom_remover_servo.right(),
            ),

            # wait a little and then remove the blue pom
            background(
                seq([
                    wait_for_seconds(1.5),
                    Defs.pom_remover_servo.yeet_blue_pom(),
                    Defs.pom_remover_servo.drum_moving_pos(),
                ]),
            ),

            drive_forward(heading=0).until(
                after_cm(7)
                + over_line(Defs.front_right_ir_sensor)
                + after_cm(15)
            ),
            turn_to_heading_left(0),

            background(
                seq([
                    Defs.pom_remover_servo.drum_moving_pos(),
                    Defs.lift_drums_servo.down(),
                ]),
                name="lower_drum"
            ),

            wall_align_forward(accel_threshold=0.3),
            mark_heading_reference(),
        ])
