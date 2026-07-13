from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm


def left_lateral_line_follow():
    return (
        line_follow()
        .single(Defs.front.right, side=LineSide.LEFT)
        .move(strafe=1)
        .correct_forward()
        .hold_heading(180)
        .pid(kp=0.4, ki=0.05, kd=0.0)
    )


def left_lateral_align_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(strafe=-0.3)
        .correct_forward(hold_heading=False)
        .pid(kp=0.5, ki=0.1, kd=0.0)
    )


def follow_line():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=1)
        .hold_heading(180)
        .correct_lateral()
        .pid(kp=0.6, ki=0.1, kd=0)
    )


class M060DriveUpRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # move away from cube stack
            optimize([
                strafe_left().until(
                    over_line(Defs.rear.left)
                ),
                background(
                    arm.move_angles(sholder_deg=110, elbow_deg=-0).arm_speeds(sholder=100, elbow=200),
                ),
                drive_backward(cm=10),
                background(
                    seq([
                        arm.move_angles(0, 90, -45, speed=90),
                        arm.move_angles(0, 140, -40, speed=90),
                        Defs.arm_claw.grab(),
                    ]),
                ),
                timeout_or(
                    strafe_left().until(
                        over_line(Defs.front.right)
                        + after_cm(5)
                    ),
                    seconds=2,
                    fallback=seq([]),
                ),
                # align on front pipe
                wall_align_forward(speed=0.3,
                                   accel_threshold=10,
                                   settle_duration=0,
                                   max_duration=1,
                                   grace_period=1
                                   ),
            ])
            .cut_corners(7, cut_until=True),

            wait_for_seconds(0.4),  # wait a bit so the bot is fully still
            mark_heading_reference(),

            # drive to black line where palette with two yellow cubes is
            optimize([
                turn_left(180),

                drive_forward(heading=180).until(
                    on_black(Defs.front.right)
                ),

                # drive to the right to the pipe
                left_lateral_line_follow().until(
                    after_cm(22)
                ),
                background(
                    arm.move_angles(0, 90, -70, speed=100),
                ),

                # align and switch calibration set
                switch_calibration_set("upper"),
            ])
            .cut_corners(5, cut_until=True),

            # magical drive up ramp
            do_while_active(
                reference_step=seq([
                    drive_forward(heading=175).until(
                        (on_black(Defs.rear.left) | on_incline(13))
                    ),
                    follow_line().until(
                        after_cm(110)
                        + over_line(Defs.front.right)
                        + after_cm(5)
                    )
                ]),
                task=seq([
                    wait_for(
                        on_incline(8)
                        + after_cm(30)
                    ),
                    parallel(
                        arm.move_angles(7, 0, 0),
                        Defs.arm_claw.open(),
                    ),
                    fully_disable_servos(),
                    wait_for(on_level(3) + after_cm(15)),
                    arm.move_angles(7, 5, -1),
                    Defs.arm_claw.full_open(),
                ]),
            ),
            parallel(
                arm.move_angles(7, 90, -40),
                drive_backward(cm=10),
            ),
            Defs.arm_claw.grab(blocking=False),
            turn_to_heading_right(0),

        ])
