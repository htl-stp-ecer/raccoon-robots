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
        .hold_heading(0)
        .pid(kp=0.6, ki=0.2, kd=0.0)
    )


def forward_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.RIGHT)
        .move(forward=1)
        .correct_lateral()
        .hold_heading(0)
        .pid(kp=0.6, ki=0.3, kd=0.05)
    )

class M090PlaceSecondCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            arm.move_angles(28, 60, -40, speed=70),  # transport
            drive_forward(cm=18, heading=0),
            # place cube
            arm.move_angles(28, 40, -40, speed=70),  # place
            Defs.arm_claw.open(),
            arm.move_angles(28, 60, -50, speed=100),  # transport

            # drive back to get space to place the second cube
            parallel(
                drive_backward(cm=20, heading=0),
                seq([
                    wait_until_distance(15),
                    grab_cube_from_container(),
                ])
            ),

            #move brown cube in possiton
            arm.move_angles(31, 80, -30) #dont to in parralel with drive_forward (we might hit the other cube stack)
            .arm_speeds(
                base=60, sholder=100, elbow=200
            ),

            # move to the cube
            drive_forward(heading=0).until(
                after_cm(19)
            ),

            # place brown cube
            arm.move_angles(elbow_deg=-52, speed=70),
            wait_for_seconds(0.2),

            Defs.arm_claw.open(),
            Defs.arm_claw.grab(), #try to stop there movement of the cubes and catsh them if they are falling
            Defs.arm_claw.open(),
            arm.move_angles(elbow_deg=-50),
            drive_backward(cm=27, heading=0),
            arm.move_angles(-90, 90, 0),

        ])
