from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm


def left_lateral_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(strafe=-1)
        .correct_forward()
        .pid(kp=0.4, ki=0.05, kd=0.0)
    )


def left_lateral_align_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(strafe=-0.4)
        .correct_forward(hold_heading=False)
        .pid(kp=0.5, ki=0.1, kd=0.0)
    )


def follow_line():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=-1)
        .correct_lateral()
        .pid(kp=0.4, ki=0.05, kd=0)
    )

class M050DriveUpRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from cube stack
            arm.move_angles(sholder_deg=110, elbow_deg=-0).arm_speeds(sholder=100, elbow=200),
            drive_backward(cm=2),
            strafe_left().until(
                over_line(Defs.front.right)
                + after_cm(2)
            ),

            #align on front pipe
            wall_align_forward(speed=0.6,
                               accel_threshold=10,
                               settle_duration=0,
                               max_duration=2,
                               grace_period=2
                               ),
            mark_heading_reference(),

            # drive to black line where palette with two yellow cubes is
            background(
                seq([
                    arm.move_angles(0, 90, -45),
                    arm.move_angles(0, 140, -40, speed=150),
                    Defs.arm_claw.grab(),
                ]),
            ),
            drive_backward(heading=0).until(
                on_black(Defs.rear.left)
            ),

            # drive to the right to the pipe
            turn_to_heading_left(0),
            left_lateral_line_follow().until(
                after_cm(30)
            ),

            # align and switch calibration set
            switch_calibration_set("upper"),

            # magical drive up ramp
            drive_backward(heading=0).until(
                on_black(Defs.front.left)
                + after_cm(90)
            ),
            follow_line().until(
                on_black(Defs.front.right)
            )
        ])
