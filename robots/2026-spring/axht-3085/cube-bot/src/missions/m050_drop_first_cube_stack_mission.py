from raccoon import *

from src.mission_params import MissionParams
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.mark_heading_if_aligned import mark_heading_if_aligned


def _follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=1)
        .correct_lateral()
        .hold_heading(0)
        .pid(kp=0.7, ki=0.2, kd=0.0)
    )


def align_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=0.2)
        .correct_lateral(hold_heading=False)
        .hold_heading(0)
        .pid(kp=0.7, ki=0.2, kd=0.0)
    )


def strafe_offset(robot):
    strafe_correction = MissionParams.first_cube_line_gap.get() - 30
    robot.info(f"strafe offset = {strafe_correction:g} cm")
    if strafe_correction > 0:
        return strafe_right(cm=strafe_correction, heading=0, speed=0.5)
    elif strafe_correction < 0:
        return strafe_left(cm=abs(strafe_correction), heading=0, speed=0.5)
    else:
        return seq([])


class M050DropFirstCubeStackMission(Mission):
    def sequence(self) -> Step:
        return optimize([
            background(
                step=seq([
                    wait_for_background("arm_up"),
                    # move servo forward
                    arm.move_angles(base_deg=0, sholder_deg=113, speed=70),
                ])
            ),
            # drive to external loading dock while rotating arm
            turn_to_heading_left(0),
            _follow().until(
                after_cm(72)
            ),
            strafe_left(cm=5, heading=0, speed=0.5),
            strafe_right(cm=4, heading=0, speed=0.5),

            _follow().until(
                after_cm(50)
            ),
            parallel(
                align_line_follow().until(
                    after_seconds(0.7),
                ),
                arm.move_angles(
                    base_deg=93, speed=80
                ),
            ),
            arm.move_angles(
                base_deg=93.1, speed=80
            ),
            wait_for_seconds(0.1),  # make sure we are not moving before starting to strafe the offest cm
            mark_heading_reference(),
            defer(strafe_offset),
            turn_to_heading_right(0),

            # place cube tower
            arm.move_angles(sholder_deg=110),
            wait_for_seconds(0.2),  # a samll delay so the sholder servo is definatly on his right posission
            arm.move_angles(elbow_deg=-98, speed=150),
            wait_for_seconds(0.5),
            Defs.arm_claw.cube_stack_regrab_open(),
            # grab a gain, so if the stack is wonky we stop the momentum
            Defs.arm_claw.grab(),
            Defs.arm_claw.full_open(),
            strafe_right(cm=6, speed=0.4),
        ])
