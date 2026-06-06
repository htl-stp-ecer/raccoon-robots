from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.calibrate_analog_drive import on_analog_flank
from src.steps.drive_to_analog_target_bidirectional import drive_to_analog_target_bidirectional


def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.right,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.7,
        ki=0.3,
        kd=0.1,
    )


class M050DriveToInnerWarehouseMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # back away from first cube stack
            drive_backward(10),

            background(
                seq([
                    arm.move_angles(10, 135, -30, speed=100),
                    Defs.arm_claw.idle(),
                    wait_for_seconds(3),
                    arm.move_angles(-90, 90, 0, speed=100),
                ]),
            ),

            # drive backwards to green cube
            drive_angle(angle_deg=-120).until(
                over_line(Defs.front.right)
            ),
            backward_line_follow().until(  # hit the middle line
                on_black(Defs.rear.left)
            ),
            # drive to the black line besides the internal loading dock
            drive_forward(cm=5),
            drive_angle(angle_deg=-60).until(
                on_black(Defs.rear.left)
            ),
        ])
