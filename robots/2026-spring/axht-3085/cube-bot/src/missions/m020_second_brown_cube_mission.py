from raccoon import *

from src.hardware.defs import Defs
from src.steps.line_follow_dsl import *
from src.kinematics.arm import arm

def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front_right_light_sensor,
        speed=1,
        side=LineSide.LEFT,
        kp=0.4,
        ki=0.3,
        kd=0.0,
    )


class M020SecondBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(),

            # Align
            drive_backward().until(
                on_black(Defs.rear_left_light_sensor)
            ),

            # Position
            background(
                arm.move_angles(-90, 110, -120),
            ),
            drive_forward(17),
            strafe_left().until(
                on_black(Defs.front_right_light_sensor),
            ),
            turn_to_heading_left(0),

            # arm.move_angles(-90, 80, -75),
            # arm.move_angles(-120, 80, -75),
            arm.move_angles(-90, 80, -75),
            arm.move_angles(-90, 60, -35),
            Defs.arm_claw.full_open(),
            arm.move_angles(-90, 40, -50),
            arm.move_angles(-90, 25, -25),
            Defs.arm_claw.grab(),
            arm.move_angles(-90, 40, -50),

            arm.move_angles(-90, 45, -45),

            strafe_right().until(
                on_black(Defs.front_left_light_sensor)
            ),
        ])