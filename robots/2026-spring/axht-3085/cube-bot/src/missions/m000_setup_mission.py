from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.calibrate_analog_drive import calibrate_analog_drive, on_analog_flank
from src.steps.line_follow_dsl import lateral_follow_line_single, lateral_follow_line_single_free
from src.steps.sample_analog_between_lines import sample_analog_between_lines


class M000SetupMission(SetupMission):
    setup_time = 120

    def sequence(self) -> Sequential:
        return seq([
            fully_disable_servos(),

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
                ])
            ),

            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
            ),

            servo(Defs.arm_sholder, 25),

            wait_for_button("calibrate upper cube"),
            calibrate_analog_drive(
                Defs.et_sensor,
                set_name="upper_cube",
                speed=-0.4,
                drive_duration_s=2
            ),

            wait_for_button("calibrate cube stack"),
            calibrate_analog_drive(
                Defs.et_sensor,
                set_name="cube_stack",
                speed=-0.4,
                drive_duration_s=2
            ),

            sample_analog_between_lines(speed=0.3),

            wait_for_button("go to strart possiont"),
            mark_heading_reference(),
            #align on the black line on the right
            strafe_right().until(
                on_black(Defs.front.right)
            ),
            strafe_left().until(
                on_white(Defs.front.right)
                + after_cm(1)
            ),
            #aling witht the black line in front
            drive_forward().until(
                on_black(Defs.front.left)
            ),
            drive_backward().until(
                on_white(Defs.front.left)
                + after_cm(1)
            ),
            turn_to_heading_right(0),


            arm.move_angles(-55, 130, -110),
            fully_disable_servos(),
        ])
