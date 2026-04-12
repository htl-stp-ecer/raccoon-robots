from src.steps.drive_to_pipe import drive_to_second_pipe
from src.steps.drum_lifting_step import *
from src.steps.drum_lineup_step import lineup_drum_with_pipe


class M050DriveToOtherPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([

                # drive backward a bit so we can lift the drum
                parallel(
                    drive_backward(cm=7),
                    Defs.pom_remover_servo.center(),
                ),
                drum_lifting_up_over_limit(),

                # turn straight
                turn_to_heading_right(185),  # turning a bit more to not hit the raised loading dock

                # drive to the seconds black line
                parallel(
                    drive_backward().until(
                        over_line(Defs.front_right_ir_sensor) +
                        on_black(Defs.front_right_ir_sensor)
                    ),
                ),

                turn_to_heading_right(90),

            # turn to black line so we can start linefollowing
                # turn_right().until(
                #    on_black(Defs.front_right_ir_sensor)
                # ),

                # wait for the other bot to finish
                wait_for_checkpoint(60 + 35),

            smoothpath(
                follow_line_single(Defs.front_right_ir_sensor,
                                   kp=1,
                                   ki=0.1,
                                   kd=0.1,
                                   side=LineSide.LEFT,
                                   speed=1.0
                                   ).until(
                    on_black(Defs.front_left_ir_sensor) & on_black(Defs.front_right_ir_sensor)
                ),

                turn_to_heading_right(90 + 20),  # turn 20deg to the right
                drive_forward(12, 1),

                turn_to_heading_right(90),
                follow_line_single(
                    Defs.front_right_ir_sensor,
                    speed=1.0,
                    kp=0.7,
                    ki=0.2,
                    kd=0.1,
                    side=LineSide.RIGHT,
                ).until(after_cm(26)),  # fahre 15 cm auf der rechten Seite des Cubes vorbei
                turn_to_heading_right(90 - 20),

                drive_to_second_pipe(),
            ),
            lineup_drum_with_pipe(True),

            # eject drum mission will be executed next
        ])
