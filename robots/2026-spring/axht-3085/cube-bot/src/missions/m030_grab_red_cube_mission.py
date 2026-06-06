from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.calibrate_analog_drive import on_analog_flank


def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.left,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )


class M030GrabRedCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from shared warehouse
            strafe_right(heading=180).until(
                on_black(Defs.front_left_light_sensor)
            ),

            # move arm into position for placing brown cube on red cube
            background(
                arm.move_angles(-90, 90, -25),
            ),

            # drive to red cube
            backward_line_follow().until(
                over_line(Defs.rear.left)
                + on_analog_flank(Defs.et_sensor, set_name="cube_stack")
            ),
            turn_to_heading_left(180),

            # place down cube
            arm.move_angles(-90, 90, -90),
            Defs.arm_claw.open(speed=70),

            # drive to side and grab both cubes
            strafe_right(heading=180).until(
                over_line(Defs.rear.left)
            ),
            arm.move_angles(-90, 30, -20),

            timeout(
                step=strafe_left(heading=180).until(
                    on_black(Defs.rear.left)
                    + after_cm(1)
                ),
                seconds=5
            ),
            Defs.arm_claw.grab(),
            Defs.arm_claw.open(speed=100),
            Defs.arm_claw.grab(),

            # lift cubes
            arm.move_angles(-90, 110, -90).arm_speeds(sholder=150, elbow=100),
        ])
