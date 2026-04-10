from libstp import seq, dsl, drive_forward, on_white, follow_line_single, on_black, LineSide, after_cm, __all__
from libstp import *


from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_eject_position
from src.steps.servo_steps import push_orange_pom_away


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
             > after_cm(41)
         ),
            seq([
                wait_until_distance(37),
                #Defs.pom_remover_servo.push_blue_pom_away(),
                #Defs.pom_remover_servo.start(),
            ])
        )
    ])
