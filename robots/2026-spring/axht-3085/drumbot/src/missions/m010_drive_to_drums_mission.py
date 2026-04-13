from raccoon import *

from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(
                origin_offset_deg=90,
            ),

            background(
                step=seq([
                    # push orange pom away
                    wait_for_seconds(0.1),
                    Defs.pom_remover_servo.orange_pom_removel(),
                    fully_disable_servos(),
                ])
            ),

            wait_for_seconds(0.3),

            smooth_path(
                turn_to_heading_right(10),  # over rotate so we push the sorted poms better
                turn_to_heading_right(17),  # magic value, so we don't hit the extenal loading dock
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
                            fully_disable_servos(),
                            wait_for(on_black(Defs.front_right_ir_sensor)),
                            Defs.pom_remover_servo.left(),
                            fully_disable_servos(),
                        ]),
                    ),
                ),

                # turn straight
                turn_to_heading_right(0),

                parallel(
                    drive_forward(cm=27, heading=0),
                    Defs.drum_pusher_servo.open(),
                    seq([
                        wait_until_distance(8), #only a good guess of distance
                        drum_recover_from_over_limit(Defs.lift_drums_servo.up),
                    ]),
                ),
                drum_lifting_down(slow_mode=False),
            ),
        ])
