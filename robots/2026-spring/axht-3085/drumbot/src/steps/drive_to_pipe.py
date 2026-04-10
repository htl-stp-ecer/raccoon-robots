from raccoon import *

from src.hardware.defs import Defs


@dsl
def drive_to_first_pipe():
    return seq([
        parallel(
            drive_forward().until(
                (on_black(Defs.front_right_ir_sensor) >
                 on_white(Defs.front_right_ir_sensor)) >
                after_cm(24)
            ),
        )

    ])


@dsl
def drive_to_second_pipe():
    return seq([
        parallel(
            follow_line_single(
                Defs.front_right_ir_sensor,
                kp=0.5,
                kd=0.1,
                side=LineSide.LEFT,
            ).until(
                on_black(Defs.front_left_ir_sensor)
            ),
            turn_to_heading_right(180),
            follow_line_single(
                Defs.front_right_ir_sensor,
                kp=0.5,
                kd=0.1,
                side=LineSide.LEFT,
            ).until(
                after_forward_cm(43)
            ),
            seq([
                wait_until_distance(37),
                # Defs.pom_remover_servo.push_blue_pom_away(),
                # Defs.pom_remover_servo.start(),
            ])
        )
    ])
