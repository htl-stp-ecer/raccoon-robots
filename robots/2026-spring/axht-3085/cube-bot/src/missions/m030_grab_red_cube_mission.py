from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.calibrate_analog_drive import on_analog_flank


def forward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )


class M030GrabRedCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from shared warehouse
            strafe_left(heading=0).until(
                over_line(Defs.front.left)
            ),

            # move arm into position for placing brown cube on red cube
            background(
                arm.move_angles(90, 140, -35),
            ),

            # drive to red cube
            forward_line_follow().until(
                on_black(Defs.front.right)
                + on_analog_flank(Defs.et_sensor, set_name="cube_stack")
                #+ after_cm(1)
            ),

            # place down cube
            arm.move_angles(90, 100, -85).arm_speeds(sholder=90),
            Defs.arm_claw.open(speed=70),

            # drive to side and grab both cubes
            strafe_left(heading=0).until(
                after_cm(12)
            ),
            arm.move_angles(90, 50, -40),

            strafe_right(heading=0).until(
                after_cm(6)
            ),
            Defs.arm_claw.grab(),
            arm.move_angles(90, 60, -30, speed=100),
            arm.move_angles(90, 50, -40),
            Defs.arm_claw.open(speed=100),
            Defs.arm_claw.strong_grab(),

            # lift cubes
            background(

                arm.move_angles(90, 110, -90).arm_speeds(sholder=150, elbow=100),
                name="arm_up"
            ),
        ])
