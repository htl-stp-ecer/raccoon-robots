from raccoon import *

from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(
                origin_offset_deg=-90,
            ),

            parallel(
                drum_lifting_up(),
                seq([
                    wait_for_seconds(0.4),
                    turn_right(90),
                ]),
                seq([
                    # push orange pom away
                    wait_for_seconds(0.8),
                    Defs.pom_remover_servo.right(),
                    wait_until_degrees(60),
                    Defs.pom_remover_servo.left(),
                ]),
            ),

            parallel(
                drive_forward().until(
                    after_cm(20) +
                    over_line(Defs.front_right_ir_sensor) +
                    after_cm(27)
                ),
                seq([
                    wait_until_distance(5),
                    Defs.pom_remover_servo.right(),
                    wait_for(on_black(Defs.front_right_ir_sensor)),
                    Defs.pom_remover_servo.left(),
                ]),
                seq([
                    wait_until_distance(55),
                    drum_lifting_down(slow_mode=False),
                ])
            )
        ])
