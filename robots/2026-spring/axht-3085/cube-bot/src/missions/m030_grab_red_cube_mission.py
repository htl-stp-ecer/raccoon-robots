from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs

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
                arm.move_angles(-90, 90, -90),
            ),

            # drive to red cube
            backward_line_follow().until(
                over_line(Defs.rear.left)
                + after_cm(7.5)
            ),

            # place down cube
            Defs.arm_claw.full_open(speed=100),

            arm.move_angles(-90, 60, -70),
            Defs.arm_claw.grab(),
            wait_for_button()
        ])