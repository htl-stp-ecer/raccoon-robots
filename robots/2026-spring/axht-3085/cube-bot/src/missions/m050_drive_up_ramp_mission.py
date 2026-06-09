from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.line_follow_dsl import lateral_follow_line_single, lateral_follow_line_single_free


def left_lateral_line_follow():
    return lateral_follow_line_single(
        sensor=Defs.rear.left,
        speed=-1,
        side=LineSide.LEFT,
        kp=0.4,
        ki=0.05,
        kd=0.0,
    )


def left_lateral_align_line_follow():
    return lateral_follow_line_single_free(
        sensor=Defs.rear.left,
        speed=-0.4,
        side=LineSide.LEFT,
        kp=0.5,
        ki=0.1,
        kd=0.0,
    )


class M050DriveUpRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from cube stack
            arm.move_angles(sholder_deg=110, elbow_deg=-90).arm_speeds(sholder=100, elbow=200),
            drive_backward(cm=10),
            strafe_left().until(
                after_cm(40)
            ),

            # drive to black line where palette with two yellow cubes is
            background(
                seq([
                    arm.move_angles(0, 90, -45),
                    arm.move_angles(0, 140, -40, speed=150),
                    Defs.arm_claw.grab(),
                ]),
            ),
            drive_backward().until(
                on_black(Defs.rear.left)
            ),

            # drive to the right to the pipe
            left_lateral_line_follow().until(
                after_cm(25)
            ),
            left_lateral_align_line_follow().until(
                after_seconds(0.5)
            ),
            mark_heading_reference(origin_offset_deg=2),  # magic offset because hardware

            # align and switch calibration set
            switch_calibration_set("upper"),

            # magical drive up ramp
            drive_backward(heading=0).until(
                on_black(Defs.front.right)
                + after_cm(85)
            ),
        ])
