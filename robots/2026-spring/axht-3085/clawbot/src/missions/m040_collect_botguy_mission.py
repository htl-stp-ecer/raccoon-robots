from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.line_follow_dsl import lateral_follow_line_single_free


def backward_line_follow():
    return strafe_follow_line_single(
        Defs.front.left,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.2,
        kd=0.0,
    )

class M040CollectBotguyMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            wait_for_button(),

            # move away from black line
            drive_backward().until(
                on_white(Defs.front.left)
            ),

            # follow line to botguy pickup
            backward_line_follow().until(
                after_cm(30)
                + on_black(Defs.front.right)
            ),
            drive_backward(speed=0.3).until(
                on_white(Defs.front.right)
            ),

            # wait for completion of tray return and turn after
            wait_for_background("return_tray"),

            # push open left door
            background(
                Defs.arm_claw.p135deg()
            ),
            arm.move_angles(-45, 63, -85),
            Defs.arm_base.max_right(),

            # push away big cube
            arm.move_angles(-90, 45, -90),
            arm.move_angles(-45, 45, -90),

            # push open right door
            arm.move_angles(-80, 40, -40),    # position arm
            arm.move_angles(-45, 40, -40),    # push open the door

            arm.move_angles(-90, 60, -90),
            drive_forward().until(
                on_black(Defs.front.left),
            ),
            lateral_follow_line_single_free(
                sensor=Defs.front.left,
                distance_cm=20,
                speed=-1,
                side=LineSide.LEFT,
                kp=0.4,
                ki=0.05,
                kd=0.0,
            ),
            mark_heading_reference(),
            arm.move_angles(-90, 60, -83),
            drive_forward(8),
            Defs.arm_claw.soft_close(),

            # get out botguy
            arm.move_angles(-90, 75, -90),
            background(
                seq([
                    wait_for(on_black(Defs.front.right)),
                    arm.move_angles(-90, 135, -115),
                ]),
            ),
            strafe_right().until(
                over_line(Defs.front.right)
            ),
            turn_to_heading_left(90),
            wall_align_forward(accel_threshold=0.3, grace_period=0.5),
            turn_to_heading_left(90),
        ])