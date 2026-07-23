from raccoon import *
from src.hardware.defs import *
from src.hardware.tuning import LINE_THRESHOLD

class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),

            # drive out of starting box
            drive_forward(heading=0, speed=0.9).until(
                on_black(Defs.rear_left_ir_sensor, LINE_THRESHOLD)
            ),

            # turn for driving angle
            turn_to_heading_right(40),

            parallel(
                drive_forward(heading=320).until(
                    over_line(Defs.front_right_ir_sensor, LINE_THRESHOLD, LINE_THRESHOLD)
                    + after_cm(5),
                ),
                seq([
                    wait_for_seconds(0.7),
                    Defs.pom_remover_servo.left(),
                    Defs.pom_remover_servo.right(),
                    Defs.pom_remover_servo.middle(),
                ])
            ),

            # turn back to original heading
            Defs.pom_remover_servo.far_right(),
            turn_to_heading_right(0),

            # remove poms on other side
            Defs.pom_remover_servo.far_left(),
        ])
