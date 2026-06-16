from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.missions.m007_move_to_center_mission import left_lateral_line_follow
from src.steps.calibrate_analog_drive import calibrate_analog_drive, on_analog_flank
from src.steps.line_follow_dsl import lateral_follow_line_single, lateral_follow_line_single_free, strafe_follow_line_single
from src.steps.sample_analog_between_lines import sample_analog_between_lines

def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.front.left,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )

class M000SetupMission(SetupMission):
    setup_time = 90

    def sequence(self) -> Sequential:
        return seq([

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

                    wait_for_seconds(1),
                ])
            ),

            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
            ),
            #---
            #line_follow().until(
            #    (over_line(Defs.front.right)
            #     + after_cm(20))
            #    | after_seconds(6)
            #),
            # drive to line
            #mark_heading_reference(origin_offset_deg=90),
            #left_lateral_line_follow().until(
            #    after_cm(40)
            #),

            #turn_to_heading_left(0),

            #drive_backward().until(
            #    on_black(Defs.rear.left)
            #),

            ## line follow backwards to retrieve spot
            #drive_forward().until(
            #    over_line(Defs.rear.left)  # if we ever are over the line this conditio will fix it
            #    + after_cm(7)
            #),
            ## go into correct lateral position for pickup
            #strafe_right(heading=0).until(
            #    on_black(Defs.rear.left),
            #),
            #---

            servo(Defs.arm_elbow, -28),
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
