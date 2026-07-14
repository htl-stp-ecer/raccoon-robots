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


class M040GrabRedCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from shared warehouse
            timeout_or(
                step=strafe_left(heading=0).until(
                    over_line(Defs.front.left)
                ),
                seconds=1,
                fallback=seq([
                    drive_backward(cm=7),
                    drive_forward(cm=5),
                    timeout_or(
                        strafe_left(heading=0).until(
                            over_line(Defs.front.left)
                        ),
                        seconds=5,
                        fallback=seq([
                            Defs.arm_claw.open(),
                            timeout(
                                seq([
                                    turn_to_heading_right(0),
                                    strafe_left(heading=0).until(
                                        over_line(Defs.front.left)
                                    ),
                                ]),
                                seconds=2,
                            )
                        ])
                    ),
                ])
            ),

            # move arm into position for placing brown cube on red cube
            background(
                arm.move_angles(83, 140, -35, speed=120),
            ),

            # drive to red cube
            turn_to_heading_left(0, speed=0.4),
            forward_line_follow().until(
                on_black(Defs.front.right)
                + after_cm(1)
            ),

            # place down cube
            arm.move_angles(elbow_deg=-97, sholder_deg=120, speed=150),
            wait_for_seconds(0.2),
            arm.move_angles(sholder_deg=109, speed=150),

            # let cube go
            Defs.arm_claw.full_open(180),
            arm.move_angles(sholder_deg=120, speed=250),
            # make sure we move claw a bit back so we dont hit the lower cube

            # grab both cubes
            arm.move_angles(elbow_deg=-82, speed=180),
            wait_for_seconds(0.3),
            arm.move_angles(sholder_deg=76, speed=180),
            Defs.arm_claw.strong_grab(),
            background(
                arm.move_angles(elbow_deg=-45).arm_speeds(base=70,
                                                          elbow=130),
            ),

            # drive to the side so we dont hit thing when we place cube back town for regreab
            timeout_or(
                strafe_left(heading=0).until(
                    on_black(Defs.rear.left)
                ),
                seconds=2,
                fallback=seq([
                    Defs.arm_claw.full_open(),
                    strafe_left(heading=0).until(
                        on_black(Defs.rear.left)
                    ),
                ]),
            ),
        ])
