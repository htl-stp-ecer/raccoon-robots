from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.calibrate_analog_drive import calibrate_analog_drive
from src.steps.custom_calibrate import custom_calibrate


class M000SetupMission(SetupMission):
    setup_time = 120

    def sequence(self) -> Sequential:
        return seq([
            pause_setup_timer(),
            fully_disable_servos(),

            wait_for_button("move servos into starting position"),
            start_setup_timer(),

            # arm start position
            background(
                seq([
                    Defs.arm_claw.idle(),
                    # TODO: Im sorry but me don't care about raccon not letting me do my servo shit (fix it some day) LG Matthias
                    # ok :)👍
                    arm.move_angles(0, 90, -90),
                    servo(Defs.arm_sholder, 25),
                    servo(Defs.arm_elbow, -28),

                    wait_for_seconds(1),
                    fully_disable_servos(),
                ])
            ),

            custom_calibrate(
                distance_cm=130,
                calibration_sets=["default"],
                ema_alpha=0.3
            ),

            wait_for_button("calibrate lower cube"),
            calibrate_analog_drive(Defs.et_sensor,
                                   set_name="lower_cube",
                                   speed=-0.4,
                                   drive_duration_s=2
                                   ),

            wait_for_button("calibrate upper cube"),
            mark_heading_reference(),
            calibrate_analog_drive(Defs.et_sensor,
                                   set_name="upper_cube",
                                   speed=0.4,
                                   drive_duration_s=2
                                   ),

            custom_calibrate(
                sensor_drive_cm=90,
                calibrate_distance=False,
                calibration_sets=["upper"],
            ),

            wait_for_button("drive into starting box"),
            drive_backward().until(
                over_line(Defs.rear.left)
            ),
            turn_to_heading_right(90),
            drive_backward().until(
                on_black(Defs.front.right)
            ),
            strafe_left().until( #stras into line
                over_line(Defs.front.right)
                + after_cm(2)
            ),
            drive_forward(cm=9),
            arm.move_angles(-30, 130, -110),

            fully_disable_servos(),

        ])
