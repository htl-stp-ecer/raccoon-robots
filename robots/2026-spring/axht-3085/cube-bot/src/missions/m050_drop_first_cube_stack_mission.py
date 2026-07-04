from raccoon import *

from src.kinematics.arm import arm
from src.hardware.defs import Defs


def _follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=1)
        .correct_lateral()
        .hold_heading(0)
        .pid(kp=0.3, ki=0.2, kd=0.0)
    )


def align_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=0.4)
        .correct_lateral(hold_heading=False)
        .hold_heading(0)
        .pid(kp=0.4, ki=0.2, kd=0.0)
    )


class M050DropFirstCubeStackMission(Mission):
    def sequence(self) -> Step:
        return optimize([
            background(
                step=seq([
                    wait_for_background("arm_up"),
                    # move servo forward
                    arm.move_angles(base_deg=0, sholder_deg=113).arm_speeds(base=70),
                ])
            ),
            # drive to external loading dock while rotating arm
            turn_to_heading_left(0),
            _follow().until(
                after_cm(67)
            ),
            #make sure  we push the poms to the side so we don't move them
            strafe_left(cm=5, heading=0),
            strafe_right(cm=4, heading=0),

            _follow().until(
                after_cm(60)
            ),
            mark_heading_reference(),
            parallel(
                align_line_follow().until(
                    after_seconds(0.4),
                ),
                arm.move_angles(
                    base_deg=90, speed=80
                ),
            ),
            strafe_left(heading=0).until(
                on_black(Defs.rear.left)
            ),
            strafe_right(heading=0).until(
                over_line(Defs.rear.left)
            ),
            turn_to_heading_right(0),

            # place cube tower
            arm.move_angles(sholder_deg=110),
            wait_for_seconds(0.2), #a samll delay so the sholder servo is definatly on his right posission
            arm.move_angles(elbow_deg=-98, speed=150),
            wait_for_seconds(0.5),
            Defs.arm_claw.open(),
            #grab a gain, so if the stack is wonky we stop the momentum
            Defs.arm_claw.grab(),
            Defs.arm_claw.full_open(),
        ])
