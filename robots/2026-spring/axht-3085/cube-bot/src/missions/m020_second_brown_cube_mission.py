from raccoon import *
from src.hardware.defs import Defs
from src.steps.line_follow_dsl import *
from src.kinematics.arm import arm
from src.steps.arm_steps import *


def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front_left_light_sensor,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )

class M020SecondBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            background(
                # move arm into starting position again
                seq([
                    arm.move_angles(0, 65, 0),
                    arm.move_angles(0, 110, -120),
                    Defs.arm_claw.idle(),
                ]),
            ),

            parallel(
                # start moving arm by 90° as soon as black line was crossed
                seq([
                    wait_for(
                        over_line(Defs.rear_left_light_sensor)
                    ),
                    arm.move_angles(-90, 110, -120),
                ]),

                # drive forward to 2nd cube pickup
                seq([
                    line_follow().until(
                        over_line(Defs.rear_left_light_sensor)
                        + after_cm(14.5)
                    ),
                ]),
            ),

            # go into correct lateral position for pickup
            strafe_left().until(
                on_black(Defs.front_right_light_sensor),
            ),

            grab_brown_cube(),


        ])
