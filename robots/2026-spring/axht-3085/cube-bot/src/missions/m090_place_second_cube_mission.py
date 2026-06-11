from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import grab_cube_from_container
from src.steps.line_follow_dsl import strafe_follow_line_single_free


def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.rear.left,
        speed=-1,
        side=LineSide.LEFT,
        kp=0.6,
        ki=0.2,
        kd=0.0,
    )


def forward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.rear.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )


class M090PlaceSecondCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from wall to avoid hitting already present cube stack
            backward_line_follow().until(
                after_cm(36)
            ),

            arm.move_angles(28, 60, -50, speed=100),  # transport
            strafe_right(heading=0).until(
                after_seconds(1.5)
            ),
            drive_forward(cm=21),
            # place cube
            arm.move_angles(28, 40, -40),  # place
            Defs.arm_claw.open(),
            arm.move_angles(28, 60, -50, speed=100),  # transport

            #drive back to get space to place the second cube
            drive_backward(cm=20),

            grab_cube_from_container(),

            #move to the cube
            arm.move_angles(28, 80, -50)
            .arm_speeds(
                base=60, sholder=100, elbow=200
            ),
            drive_forward().until(
                after_cm(18)
            ),

            # place brown cube
            arm.move_angles(elbow_deg=-60, speed=80),

            Defs.arm_claw.open(),
            arm.move_angles(elbow_deg=-50),
            drive_backward(cm=20),
        ])
