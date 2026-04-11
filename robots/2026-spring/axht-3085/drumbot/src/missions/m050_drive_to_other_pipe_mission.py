from src.steps.drive_to_pipe import drive_to_second_pipe
from src.steps.drum_lifting_step import *
from src.steps.drum_lineup_step import lineup_drum_with_pipe


class M050DriveToOtherPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([

            #drive backward a bit so we can lift the drum
            parallel(
              drive_backward(cm=5),
              drum_lifting_up(),
            ),

            #turn straight
            turn_to_heading_right(180),

            #drive to the seconds black line
            parallel(
                drive_backward().until(
                    over_line(Defs.front_right_ir_sensor) +
                    on_black(Defs.front_right_ir_sensor)
                ),
            ),

            turn_to_heading_right(90),

            #turn to black line so we can start linefollowing
            turn_right().until(
                on_black(Defs.front_right_ir_sensor)
            ),

            #wait for the other bot to finish
            wait_for_checkpoint(60 + 33),

            follow_line_single(Defs.front_right_ir_sensor,
                               kp=1,
                               kd=0.1,
                               side=LineSide.RIGHT,
                               speed=1.0
                               ).until(
                on_black(Defs.front_left_ir_sensor)  +
                after_forward_cm(12)
            ),
            turn_to_heading_left(20),

            drive_to_second_pipe(),
            lineup_drum_with_pipe(),

            #eject drum mission will be executed next
        ])
