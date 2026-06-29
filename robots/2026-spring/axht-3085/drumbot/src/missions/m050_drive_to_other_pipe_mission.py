from raccoon import *
from src.steps.drive_to_pipe import drive_to_second_pipe
from src.steps.drum_lifting_step import *
from src.steps.drum_lineup_step import lineup_drum_with_pipe
from src.steps.drum_collector import eject_nearest_color
from src.steps.drum_collector import drum_retreat


class M050DriveToOtherPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # drive backward a bit so we can lift the drum
            drive_backward(cm=10),

            # start lifting up drum
            background(
                Defs.lift_drums_servo.up(50),
            ),

            # turn straight
            turn_to_heading_right(185),  # in order to not hit the raised loading dock

            # drive to the seconds black line
            drive_backward().until(
                on_black(Defs.front_right_ir_sensor)
            ),

            turn_to_heading_right(90),

            # turn to black line so we can start linefollowing
            # turn_right().until(
            #    on_black(Defs.front_right_ir_sensor)
            # ),

            # line follow forward
            follow_line_single(
                sensor=Defs.front_right_ir_sensor,
                speed=1.0,
                side=LineSide.LEFT,
                kp=1,
                ki=0.1,
                kd=0.1,
            ).until(
                after_cm(60),
            ),

            # turn away and drive angled to avoid hitting wall
            turn_to_heading_right(90 - 30),
            drive_forward().until(
                after_cm(20)
                + over_line(Defs.front_right_ir_sensor)
                + after_cm(5)
            ),

            # turn onto black line
            turn_right().until(
                on_black(Defs.front_right_ir_sensor)
            ),

            # follow line until before drum pole
            follow_line_single(
                Defs.front_right_ir_sensor,
                speed=1.0,
                side=LineSide.LEFT,
                kp=2.0,
                ki=0.7,
                kd=0.1,
            ).until(
                over_line(Defs.rear_left_ir_sensor)
                + after_cm(15)
            ),

            lineup_drum_with_pipe(),
            drum_retreat(4),
        ])
