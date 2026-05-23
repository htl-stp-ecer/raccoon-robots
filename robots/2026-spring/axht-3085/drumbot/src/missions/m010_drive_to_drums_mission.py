from raccoon import *

from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(origin_offset_deg=-90),

            background(
                Defs.lift_drums_servo.up(120),
            ),

            smooth_path(
                drive_backward(heading=90).until(
                    on_black(Defs.rear_left_ir_sensor)
                ),
                turn_to_heading_left(90),
                drive_forward(12, heading=90),
                turn_to_heading_left(0),
                drive_forward(heading=0).until(
                    over_line(Defs.front_right_ir_sensor)
                    + over_line(Defs.front_right_ir_sensor)
                    + after_cm(19)
                ),
                turn_to_heading_left(0),

                correct=False,
            ),

            background(
                seq([
                    wait_for_seconds(0.1),
                    Defs.lift_drums_servo.down(),
                ]),
                name="lower_drum"
            ),

            wall_align_forward(grace_period=0.1, accel_threshold=0.3),
            turn_to_heading_left(0),
        ])


        # return seq([
        #     mark_heading_reference(
        #         origin_offset_deg=90,
        #     ),
        #
        #     background(
        #         step=seq([
        #             # push orange pom away
        #             wait_for_seconds(0.1),
        #             Defs.pom_remover_servo.orange_pom_removel(),
        #             fully_disable_servos(),
        #         ])
        #     ),
        #
        #     #wait_for_seconds(0.3),
        #
        #     smooth_path(
        #         turn_to_heading_right(16.7),  # over rotate so we push the sorted poms better value before 14
        #         turn_to_heading_right(17.8),  # magic value, so we don't hit the extenal loading dock
        #         parallel(
        #             seq([
        #                 drive_forward().until(
        #                     after_cm(20) +
        #                     over_line(Defs.front_right_ir_sensor)
        #                 ),
        #             ]),
        #             background(
        #                 step=seq([
        #                     wait_until_distance(5),
        #                     Defs.pom_remover_servo.right(),
        #                     fully_disable_servos(),
        #                     wait_until_distance(29),
        #                     Defs.pom_remover_servo.left(),
        #                     #fully_disable_servos(),
        #                     #wait_until_distance(22),
        #                     drum_recover_from_over_limit(Defs.lift_drums_servo.up),
        #                 ]),
        #             ),
        #         ),
        #
        #         # turn straight
        #         turn_to_heading_right(0),
        #
        #         parallel(
        #             drive_forward(cm=27, heading=0),
        #             Defs.drum_pusher_servo.open(),
        #             seq([
        #                 wait_until_distance(12), #only a good guess of distance
        #                 drum_lifting_down(slow_mode=False),
        #             ]),
        #         ),
        #     ),
        # ])
