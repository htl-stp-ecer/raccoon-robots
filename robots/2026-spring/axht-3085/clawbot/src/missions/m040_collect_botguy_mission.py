from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.line_follow_dsl import lateral_follow_line_single_free


def line_follow():
    return strafe_follow_line_single(
        Defs.front.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.3,
        kd=0.0,
    )

def backward_line_follow():
    return strafe_follow_line_single(
        Defs.front.left,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.3,
        kd=0.0,
    )


def left_lateral_line_follow():
    return lateral_follow_line_single_free(
        sensor=Defs.front.left,
        speed=-0.6,
        side=LineSide.LEFT,
        kp=0.4,
        ki=0.05,
        kd=0.0,
    )


class M040CollectBotguyMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from black line
            drive_backward().until(
                on_white(Defs.front.left)
            ),

            # follow line to botguy pickup
            backward_line_follow().until(
                after_cm(30)
                + over_line(Defs.front.right)
                + after_cm(2)
            ),
            line_follow().until(
                on_black(Defs.front.right)
            ),

            # wait for completion of tray return and turn after
            wait_for_background("return_tray"),

            # push open left door
            arm.move_angles(-45, 61, -80),
            background(
                Defs.arm_claw.p135deg()
            ),
            Defs.arm_base.max_right(),
            wait_for_seconds(0.5),

            # push away big cube
            arm.move_angles(-90, 45, -90),
            arm.move_angles(-45, 45, -90),

            # push open right door
            arm.move_angles(-80, 65, -90),  # position
            arm.move_angles(-80, 35, -25),  # position arm
            arm.move_angles(-45, 35, -25),  # push open the door

            arm.move_angles(-90, 60, -83),
            drive_forward().until(
                on_black(Defs.front.left),
            ),

            # align on pipe
            left_lateral_line_follow().until(
                after_cm(30),
            ),
            mark_heading_reference(),

            drive_forward(3),
            Defs.arm_claw.soft_close(),

            # get out botguy
            arm.move_angles(-90, 75, -90),
            background(
                seq([
                    #start pulling out botguy when we hit black line
                    wait_for(on_black(Defs.front.right)),
                    arm.move_angles(-90, 135, -115),
                ]),
            ),

            smooth_path(
                seq([
                    # turn_to_heading_left(0), done with the heading parameter of strafe
                    strafe_right(heading=0).until(
                        over_line(Defs.front.right)
                    ),

                    #turn the bot the pipe and # make sure we are not blocking the oter bot
                    #turn_to_heading_left(90), # done with heading of drive forward
                    drive_forward(heading=90).until(
                        on_black(Defs.rear.left)
                    ),
                ]),
            ),
        ])
