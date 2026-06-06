from raccoon import *
from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(origin_offset_deg=-90),

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
