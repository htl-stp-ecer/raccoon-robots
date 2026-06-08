from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.line_follow_dsl import lateral_follow_line_single

def right_lateral_line_follow():
    return lateral_follow_line_single(
        sensor=Defs.front.right,
        speed=1,
        side=LineSide.LEFT,
        kp=0.4,
        ki=0.05,
        kd=0.0,
    )

class M050DriveUpRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from cube stack
            parallel(
                arm.move_angles(elbow_deg=0),
                strafe_left().until(
                    after_cm(35)
                ),
            ),

            # drive to black line where palette with two yellow cubes is
            turn_to_heading_right(180),
            drive_forward().until(
                on_black(Defs.front.right)
            ),

            # drive to the right to the pipe
            right_lateral_line_follow().until(
                after_cm(20)
            ),

            # align and switch calibration set
            turn_to_heading_left(175),
            switch_calibration_set("upper"),

            # move arm while driving
            background(
                seq([
                    wait_for(on_black(Defs.rear.left)),
                    arm.move_angles(0, 80, -80),
                ]),
            ),

            # stuff
            smooth_path(
                drive_forward(heading=175).until(
                    on_black(Defs.rear.left)
                    + after_cm(10)
                ),
                drive_forward(cm=80, heading=180),

                background(
                    arm.move_angles(-50, 80, -80),
                ),
                strafe_left(heading=0).until(
                    on_black(Defs.front.left)
                    | after_seconds(2)
                ),
            ),
        ])