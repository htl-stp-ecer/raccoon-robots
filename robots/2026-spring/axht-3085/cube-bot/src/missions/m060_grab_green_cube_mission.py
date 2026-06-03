from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm


class M060GrabGreenCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            background(
                parallel(
                    arm.move_angles(-90, 90, 0, speed=100),
                    Defs.arm_claw.idle(),
                ),
            ),

            # align for moving cube
            drive_forward(10, heading=0),
            strafe_right(heading=0).until(
                over_line(Defs.front.right)
            ),

            # put claw onto cube
            arm.move_angles(-90, 40, -20),

            # move cube
            drive_backward(20, heading=0),

            # get ready for grabbing palette with cube
            arm.move_angles(-90, 60, 0),
            Defs.arm_claw.full_open(),
            strafe_right(2),
            drive_backward(4),

            # position arm and grab
            arm.move_angles(-90, 25, -20),
            strafe_left(5),
            arm.move_angles(elbow_deg=-30),
            loop_for(
                seq([
                    Defs.arm_claw.grab(),
                    Defs.arm_claw.full_open(),
                ]),
                iterations=2
            ),
            Defs.arm_claw.strong_grab(),

            # lift palette with cube
            arm.move_angles(-90, 60, -50),
        ])