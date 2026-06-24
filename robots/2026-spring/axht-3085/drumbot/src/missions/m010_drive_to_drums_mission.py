from raccoon import *
from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),

            # drive out of starting box
            drive_forward(heading=0, speed=0.9).until(
                on_black(Defs.rear_left_ir_sensor)
            ),

            # turn drive turn
            turn_right(40),
            drive_forward().until(
                over_line(Defs.front_right_ir_sensor)
                + after_cm(7),
            ),

            # wait a little and then remove the blue pom
            background(
                seq([
                    Defs.pom_remover_servo.right(),
                    Defs.pom_remover_servo.drum_moving_pos(),
                ]),
                name="yeet_blue_pom",
            ),

            # turn back to original heading
            turn_to_heading_right(0),

            # wait and lower drum
            background(
                seq([
                    wait_for_seconds(0.5),
                    parallel(
                        Defs.lift_drums_servo.down(),
                        Defs.drum_pusher_servo.open(),
                    ),
                ]),
                name="lower_drum",
            ),

            wait_for_background("yeet_blue_pom"),

            wall_align_forward(
                accel_threshold=0.3,
                grace_period=0.35
            ),
            mark_heading_reference(),
        ])
