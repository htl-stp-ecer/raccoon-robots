from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm

def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front_right_light_sensor,
        speed=-1,
        side=LineSide.LEFT,
        kp=0.8,
        ki=0.3,
        kd=0.2,
    )

class M010FirstBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # align to black line linear
            drive_forward().until(
                on_black(Defs.front_right_light_sensor)
            ),
            drive_backward().until(
                on_white(Defs.front_right_light_sensor)
                + after_cm(1)
            ),

            # linefollow backwards to retrieve spot
            backward_line_follow().until(
                after_cm(12)
            ),

            arm.move_angles(-90, 110, -120),     # rotate left to face correct direction
            arm.move_angles(-90, 80, -75),       # move into shared area
            arm.move_angles(-90, 60, -40),       # move further into shared area
            Defs.arm_claw.full_open(),           # open claw
            arm.move_angles(-90, 30, -35),       # move down
            Defs.arm_claw.grab(),                # grab cube

            arm.move_angles(-90, 60, -40),       # lift up again
            arm.move_angles(-90, 110, -120),     # move out of shared area

            # move away from shared warehouse
            strafe_right().until(
                on_black(Defs.front_left_light_sensor)
            ),

            arm.move_angles(

            ),
        ])