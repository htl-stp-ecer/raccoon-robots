from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.calibrate_analog_drive import on_analog_flank


def forward_line_follow():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=1)
        .correct_lateral()
        .pid(kp=0.6, ki=0.1, kd=0.05)
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
                arm.move_angles(75, 140, -35),
            ),

            # drive to red cube
            forward_line_follow().until(
                on_black(Defs.front.right)
            ),

            # place down cube
            arm.move_angles(75, 99, -87),
            Defs.arm_claw.full_open(),
            wait_for_seconds(0.5),
            arm.move_angles(75, 75, -80),
            Defs.arm_claw.strong_grab(),
            background(
                arm.move_angles(base_deg=91,elbow_deg=-45).arm_speeds(base=70),
            ),

            #drive to the side so we dont hit thing when we place cube back town for regreab
            strafe_left(heading=0).until(
                on_black(Defs.rear.left)
            ),
            #place cube down and regrab
            #Defs.arm_claw.full_open(speed=100),
            #wait_for_seconds(0.3),
            #Defs.arm_claw.strong_grab(),

            # lift cubes
            background(

                arm.move_angles(90, 110, -90).arm_speeds(sholder=150, elbow=100),
                name="arm_up"
            ),
        ])
