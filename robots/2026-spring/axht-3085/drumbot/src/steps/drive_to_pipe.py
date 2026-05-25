from raccoon import *

from src.hardware.defs import Defs
from src.steps.drum_lifting_step import drum_recover_from_over_limit


@dsl
def drive_to_second_pipe():
    def line_follower():
        return follow_line_single(
            Defs.front_right_ir_sensor,
            speed=1.0,
            kp=0.7,
            ki=0.2,
            kd=0.1,
            side=LineSide.LEFT,
        )

    return seq([
        #line_follower().until(
            # after_cm(20) +
        #    over_line(Defs.rear_left_ir_sensor) +
        #    after_cm(14),   #eventuell wall alignen testen
        #),

        # make sure we are straight (to drive accurace distance
        parallel(
            drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
            Defs.pom_remover_servo.left(),
        ),

        #drive_forward(36,0.7),
        # TODO: Try a drive straight and align on pipe
        #parallel(
        #wall_align_forward(accel_threshold=10, grace_period=0.5, max_duration=3),
        #    Defs.pom_remover_servo.left(),
        #),
        #parallel(
        #    drive_backward(cm=16),
        #    drum_recover_from_over_limit(Defs.lift_drums_servo.seek_position),
        #),
    ])
