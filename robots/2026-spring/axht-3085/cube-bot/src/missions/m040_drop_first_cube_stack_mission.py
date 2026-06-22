from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs


def _follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=1)
        .correct_lateral()
        .pid(kp=0.3, ki=0.1, kd=0.0)
    )


def align_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=0.4)
        .correct_lateral(hold_heading=False)
        .pid(kp=0.4, ki=0.2, kd=0.0)
    )


class M040DropFirstCubeStackMission(Mission):
    def sequence(self) -> Sequential:
        return optimize([
            background(
                step=seq([
                    wait_for_background("arm_up"),
                    # move servo forward
                    arm.move_angles(base_deg=0, sholder_deg=113).arm_speeds(base=70),
                ])
            ),

            # drive to external loading dock while rotating arm
            _follow().until(
                after_cm(135)
            ),
            parallel(
                align_line_follow().until(
                    after_seconds(0.6),
                ),
                arm.move_angles(
                    base_deg=90, speed=80
                ),
            ),
            #mark_heading_reference(), commented the mark heading referenc since we usually are on a pom and dont are accact
            turn_to_heading_right(0),
            strafe_left(heading=0, speed=0.5).until(
                on_black(Defs.rear.left)
            ),
            strafe_right(heading=0, speed=0.5).until(
                on_white(Defs.rear.left)
            ),
            turn_to_heading_right(0),

            # place cube tower
            arm.move_angles(sholder_deg=113),
            wait_for_seconds(0.2), #a samll delay so the sholder servo is definatly on his right posission
            arm.move_angles(elbow_deg=-98, speed=150),
            wait_for_seconds(0.5),
            Defs.arm_claw.open(),
        ])
