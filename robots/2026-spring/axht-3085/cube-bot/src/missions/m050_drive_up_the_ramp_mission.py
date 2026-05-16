from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.line_follow_dsl import lateral_follow_line_single_free, lateral_follow_line_single


def left_lateral_line_follow():
    return lateral_follow_line_single(
        sensor=Defs.rear.left,
        distance_cm=100,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.1,
        kd=0.0,
    )


def right_lateral_line_follow():
    return lateral_follow_line_single(
        sensor=Defs.front.right,
        speed=1,
        side=LineSide.LEFT,
        kp=0.4,
        ki=0.05,
        kd=0.0,
    )


def forward_line_follow():
    return strafe_follow_line_single(
        Defs.front_left_light_sensor,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.3,
        kd=0.0,
    )


class M050DriveUpTheRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # follow the line to starting box
            left_lateral_line_follow().until(
                after_cm(90)
            ),
            smooth_path(
              seq([
                  turn_to_heading_left(90), #make sure we keep our rotation

                  drive_backward(heading=90).until(
                      after_cm(10)
                      + over_line(Defs.front.left)
                  ),

                  #turn_to_heading_right(0), #turn to ramp --> doen with heading of drive_forward
                  drive_forward(heading=0).until(
                      on_black(Defs.front.right)
                  ),

              ])
            ),
            # align on pipe
            right_lateral_line_follow().until(
                after_cm(30)
            ),

            # drive the up the ramp
            switch_calibration_set("upper"),
            background(
                seq([
                    wait_for(on_black(Defs.rear.left)),
                    arm.move_angles(0, 80, -80),
                ]),
            ),

            # drive up the ramp
            smooth_path(
                drive_forward(heading=-5).until(
                    on_black(Defs.rear.left)
                    + after_cm(10)
                ),
                drive_forward(cm=80, heading=0),

                background(
                    step=arm.move_angles(-50, 80, -80),
                ),
                strafe_left(heading=0).until(
                    on_black(Defs.front.left)
                    | after_seconds(2)
                ),
            ),

            forward_line_follow().until(
                over_line(Defs.front.right)
            )

        ])
