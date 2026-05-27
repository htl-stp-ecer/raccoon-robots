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

def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.rear_left_light_sensor,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )

class M020SecondBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move arm into starting position again
            background(
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
            strafe_left(heading=180).until(
                on_black(Defs.front_right_light_sensor),
            ),

            grab_brown_cube(),

            # move away from shared warehouse
            strafe_right(heading=180).until(
                over_line(Defs.front_left_light_sensor)
            ),

            # move arm into position for placing brown cube on red cube
            background(
                arm.move_angles(-90, 90, -80),
            ),

            # drive to red cube
            backward_line_follow().until(
                over_line(Defs.rear_left_light_sensor)
                + after_cm(5.5)
            ),

            # strafe to position brown over red
            strafe_left(heading=180).until(
                on_black(Defs.front_left_light_sensor)
                + after_cm(1)
            ),

            # place down cube
            Defs.arm_claw.full_open(speed=100),

            # pick up red & brown stack
            strafe_right(heading=180).until(
                on_black(Defs.rear_left_light_sensor)
            ),
            arm.move_angles(-90, 60, -40),
            Defs.arm_claw.grab(),
        ])
