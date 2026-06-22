from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import grab_cube_from_container


def backward_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=-1)
        .correct_lateral()
        .pid(kp=0.6, ki=0.2, kd=0.0)
    )


def forward_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.RIGHT)
        .move(forward=1)
        .correct_lateral()
        .pid(kp=0.6, ki=0.3, kd=0.05)
    )


class M090PlaceSecondCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from wall to avoid hitting already present cube stack
            drive_backward(heading=0).until(
                after_cm(27)
            ),

            arm.move_angles(26, 60, -50, speed=70),  # transport
            drive_forward(cm=18, heading=0),
            # place cube
            arm.move_angles(26, 40, -40),  # place
            Defs.arm_claw.open(),
            arm.move_angles(26, 60, -50, speed=100),  # transport

            # drive back to get space to place the second cube
            drive_backward(cm=20, heading=0),

            grab_cube_from_container(),

            arm.move_angles(26, 80, -50) #dont to in parralel with drive_forward (we might hit the other cube stack)
            .arm_speeds(
                base=60, sholder=100, elbow=200
            ),

            # move to the cube
            drive_forward(heading=0).until(
                after_cm(19)
            ),

            # place brown cube
            arm.move_angles(elbow_deg=-55, speed=80),

            Defs.arm_claw.open(),
            arm.move_angles(elbow_deg=-50),
            drive_backward(cm=34, heading=0),
            arm.move_angles(-90, 90, 0),

        ])
