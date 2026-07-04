from raccoon import *
from src.steps.drum_lineup_step import lineup_drum_with_pipe
from src.steps.drum_collector import drum_retreat
from src.steps.pom_pusher_servo_moves import *

class M040DriveToOtherPipeMission(Mission):
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

            # turn parallel to black line
            turn_to_heading_right(90),

            pom_pusher_rubber_band_avoid_pos(),

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

            pom_pusher_obstacle_avoid_pos(),

            lineup_drum_with_pipe(),
            drum_retreat(4),

            # turn away and tuck in drum to finish off everything
            parallel(
                turn_left(45),
                seq([
                    wait_for_seconds(0.2),
                    Defs.lift_drums_servo.over_limit(120),
                ]),
            ),
        ])
