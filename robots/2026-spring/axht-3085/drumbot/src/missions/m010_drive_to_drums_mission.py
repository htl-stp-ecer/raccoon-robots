from raccoon import *

from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(
                origin_offset_deg=90,
            ),

            parallel(
                drum_lifting_up(),
                seq([
                    wait_for_seconds(0.3),
                    #turn_left(90),  # magic value, so we push the orange sorted poms correctly
                    turn_to_heading_right(15),  # magic value, so we dont hit the extenal loading dock
                ]),
                background(
                    step=seq([
                        # push orange pom away
                        wait_for_seconds(0.1),
                        Defs.pom_remover_servo.orange_pom_removel(),
                    ])
                ),
            ),

            parallel(
                seq([
                    drive_forward().until(
                        after_cm(20) +
                        over_line(Defs.front_right_ir_sensor)
                    ),
                ]),
                background(
                    step=seq([
                        wait_until_distance(5),
                        Defs.pom_remover_servo.right(),
                        wait_for(on_black(Defs.front_right_ir_sensor)),
                        Defs.pom_remover_servo.left(),
                    ]),
                ),
            ),

            #turn straight
            turn_to_heading_right(0),

            parallel(
                drive_forward(cm=27),
                seq([
                    wait_until_distance(8),
                    drum_lifting_down(slow_mode=False),
                ])
            ),
        ])
