from raccoon import *
from src.hardware.defs import Defs
from src.steps.drum_lineup_step import lineup_drum_with_pipe
from src.steps.drum_collector import drum_retreat
from src.steps.pom_pusher_servo_moves import *

class M040DriveToOtherPipeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # drive backward a bit so we can lift the drum
            #drive_backward(cm=10),

            # start lifting up drum
            #background(
            #    Defs.lift_drums_servo.up(50),
           # ),

            parallel(
              turn_to_heading_right(90),
                Defs.lift_drums_servo.up(50),
            ),

            #drive until we are on the black tape in front of the ramp
            drive_forward(heading=270).until(
              on_black(Defs.front_right_ir_sensor)
            ),

            drive_backward().until(
                on_white(Defs.front_right_ir_sensor)
                + after_cm(6)
            ),
            turn_to_heading_right(180),


            # turn straight
            #turn_to_heading_right(185),  # in order to not hit the raised loading dock

            # drive to the seconds black line
            drive_backward().until(
                on_black(Defs.front_right_ir_sensor)
            ),

            # turn parallel to black line
            turn_to_heading_right(90),

            background(
                pom_pusher_rubber_band_avoid_pos(),
            ),

            # line follow forward
            follow_line_single(
                sensor=Defs.front_right_ir_sensor,
                speed=1.0,
                side=LineSide.LEFT,
                kp=1,
                ki=0.1,
                kd=0.1,
            ).until(
                after_cm(61),
            ),

            # turn away and drive angled to avoid hitting wall
            turn_to_heading_right(90 - 33),
            drive_forward().until(
                after_cm(20)
                + over_line(Defs.front_right_ir_sensor)
                + after_cm(5)
            ),

            # attempt to knock any cones infront of the robot to the side
            background(
                seq([
                    Defs.pom_remover_servo.left(),
                    wait_for(
                        on_black(Defs.front_right_ir_sensor)
                    ),
                    Defs.pom_remover_servo.knock_cone_pos(),
                    Defs.pom_remover_servo.right(),
                ])
            ),

            # turn onto black line
            turn_right().until(
                on_black(Defs.front_right_ir_sensor)
            ),

            background(
                seq([
                    wait_for(
                        on_black(Defs.rear_left_ir_sensor)
                    ),
                    pom_pusher_obstacle_avoid_pos(),
                ]),
            ),

            # follow line until before drum pole
            follow_line_single(
                Defs.front_right_ir_sensor,
                speed=1.0,
                side=LineSide.LEFT,
                kp=2.0,
                ki=0.4,
                kd=0.1,
            ).until(
                over_line(Defs.rear_left_ir_sensor)
                + after_cm(13)
            ),

            lineup_drum_with_pipe(),
            drum_retreat(
                count=4,
                velocity_factor=0.6
            ),
        ])
