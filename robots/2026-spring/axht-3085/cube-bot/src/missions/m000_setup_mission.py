from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.calibrate_analog_drive import calibrate_analog_drive
from src.steps.line_follow_dsl import lateral_follow_line_single, lateral_follow_line_single_free


def right_lateral_line_follow():
    return lateral_follow_line_single(
        sensor=Defs.front.right,
        speed=1,
        side=LineSide.LEFT,
        kp=0.4,
        ki=0.05,
        kd=0.0,
    )

def right_lateral_align_line_follow():
    return lateral_follow_line_single_free(
        sensor=Defs.front.right,
        speed=0.4,
        side=LineSide.LEFT,
        kp=0.5,
        ki=0.1,
        kd=0.0,
    )


class M000SetupMission(SetupMission):
    setup_time = 120

    def sequence(self) -> Sequential:
        return seq([
            fully_disable_servos(),
            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
                ema_alpha=0.9
            ),

            wait_for_button("init"),
            arm.move_angles(91, 75, -55, speed=150),

            wait_for_button("go"),
            mark_heading_reference(),

            #########

            # move away from cube stack
            parallel(
                arm.move_angles(elbow_deg=0),
                strafe_left().until(
                    after_cm(30)
                ),
            ),

            # drive to black line where palette with two yellow cubes is
            turn_to_heading_right(180),
            background(
                arm.move_angles(0, 90, -45),
            ),
            drive_forward().until(
                on_black(Defs.front.right)
            ),

            # drive to the right to the pipe
            right_lateral_line_follow().until(
                after_cm(25)
            ),
            right_lateral_align_line_follow().until(
                after_seconds(0.5)
            ),
            mark_heading_reference(origin_offset_deg=180),

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

            # magical drive up ramp
            smooth_path(
                drive_forward(heading=175).until(
                    on_black(Defs.rear.left)
                    + after_cm(10)
                ),
                background(
                    seq([
                        arm.move_angles(0, 10, 0),
                        Defs.arm_claw.full_open(),
                        # fully_disable_servos(),
                    ]),
                ),
                drive_forward(cm=80, heading=180),
            ),

            # strafe_left(heading=180).until(
            #     on_black(Defs.front.left)
            #     | after_seconds(2)
            # ),
            drive_forward(heading=180).until(
                over_line(Defs.front.right)
            ),
            arm.move_angles(0, 90, -30),

            drive_backward(heading=180).until(
                after_cm(45)
            ),

            turn_to_heading_left(0),

            strafe_right(heading=0).until(
                over_line(Defs.rear.left)
            ),

            arm.move_angles(28, 62, -50),

            #########

            wait_for_button("end"),

            pause_setup_timer(),
            fully_disable_servos(),

            wait_for_button("move servos into starting position"),
            start_setup_timer(),

            mark_heading_reference(),

            # arm start position
            background(
                seq([
                    # TODO: Im sorry but me don't care about raccoon not letting me do my servo shit (fix it some day) LG Matthias
                    # ok :) 👍

                    Defs.arm_claw.idle(),
                    arm.move_angles(0, 110, -90),
                    servo(Defs.arm_elbow, -28),

                    wait_for_seconds(1),
                    fully_disable_servos(),
                ])
            ),

            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
                ema_alpha=0.9
            ),

            servo(Defs.arm_sholder, 25),

            # wait_for_button("calibrate lower cube"),
            # calibrate_analog_drive(
            #    Defs.et_sensor,
            #    set_name="lower_cube",
            #    speed=-0.4,
            #    drive_duration_s=2
            # ),

            wait_for_button("calibrate cube stack"),
            calibrate_analog_drive(
                Defs.et_sensor,
                set_name="cube_stack",
                speed=0.4,
                drive_duration_s=2
            ),

            # wait_for_button("calibrate upper cube"),
            # mark_heading_reference(),
            # calibrate_analog_drive(
            #    Defs.et_sensor,
            #    set_name="upper_cube",
            #    speed=0.4,
            #    drive_duration_s=2
            # ),

            arm.move_angles(-30, 130, -110),
            fully_disable_servos(),
        ])
