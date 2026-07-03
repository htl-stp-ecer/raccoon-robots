from raccoon import *
from src.hardware.defs import *
from src.steps.drum_lifting_step import *


class M010DriveToDrumsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),

            # drive out of starting box
            drive_forward(heading=0, speed=0.9).until(
                on_black(Defs.rear_left_ir_sensor)
            ),

            # turn for driving angle
            turn_to_heading_right(40),

            # drive
            drive_forward(heading=320).until(
                over_line(Defs.front_right_ir_sensor)
                + after_cm(5),
            ),

            # remove any poms that might be in front of the robot
            background(
                seq([
                    wait_for_seconds(0.3),
                    Defs.pom_remover_servo.right(),
                    Defs.pom_remover_servo.drum_moving_pos(),
                ]),
                name="yeet_blue_pom",
            ),

            # turn back to original heading
            turn_to_heading_right(0),

            # in order to avoid damaging pom pusher by sandwiching it between the pipes and the bot
            wait_for_background("yeet_blue_pom"),
        ])
