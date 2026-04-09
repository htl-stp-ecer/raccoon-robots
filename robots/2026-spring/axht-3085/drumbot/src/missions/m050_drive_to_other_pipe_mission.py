from src.steps.drive_to_pipe import drive_to_second_pipe
from src.steps.drum_lifting_step import *
from src.steps.drum_lineup_step import  lineup_drum_with_pipe


class M050DriveToOtherPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([

            parallel(drive_backward(7, 1), drum_lifting_up()),
            turn_to_heading_left(90),
            drive_backward().until(
                after_cm(40) >
                on_black(Defs.front_right_ir_sensor)

            ),
            # drive_backward(40, 1),
            # drive_backward().until(on_black(Defs.front_right_ir_sensor)),
            drive_forward(2.5, 1),
            turn_left().until(on_black(Defs.front_right_ir_sensor)),
            wait_for_checkpoint(60 + 33),

            follow_line_single(Defs.front_right_ir_sensor, kp=1, kd=0.1, side=LineSide.RIGHT, speed=1.0).until(
                on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor) >
                after_cm(12)
            ),
            turn_to_heading_right(160),
            # turn_left(20,1),
            # drive_forward(8, 1),

            #  follow_line_single(Defs.front_right_ir_sensor, kp=0.3, kd=0.1, side=LineSide.RIGHT).until(
            #    on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor)),
            # drive_forward(12, 1),

            drive_to_second_pipe(),
            lineup_drum_with_pipe(),
        ])
