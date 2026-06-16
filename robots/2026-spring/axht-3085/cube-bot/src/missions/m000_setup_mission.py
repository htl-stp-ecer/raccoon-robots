from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.calibrate_analog_drive import calibrate_analog_drive
from src.steps.setup_calibration import CalibrationAxis, calibration_gate, collect_drive, collect_ir_set


class M000SetupMission(SetupMission):
    setup_time = 90

    async def pre_start_gate(self, robot) -> None:
        await calibration_gate().run_step(robot)
        await robot._pre_start_gate()

    def sequence(self) -> Sequential:
        return seq([
            # auto_tune(
            #     tune_bemf_velocity=True,
            #     tune_vel_lpf=False,
            #     tune_static_friction=False,
            #     tune_firmware_pid=False,
            #     tune_encoder_cal=True,
            #     tune_characterize=False,
            #     tune_velocity=False,
            #     tune_motion=False,
            #     tune_tolerances=False,
            #     motion_axes=["distance", "lateral", "heading"],
            #     step_confirm=True,
            #     persist=True,
            # ),
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

            wait_for_button("calibrate lower distance"),
            collect_drive(
                collect_ir_set(
                    drive_forward(cm=50),
                    set_name="default",
                ),
            ),


            servo(Defs.arm_elbow, -28),
            servo(Defs.arm_sholder, 25),

            wait_for_button("calibrate upper ir"),
            collect_ir_set(
                drive_forward(cm=50),
                set_name="upper",
            ),

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

            calibration_gate(
                require_axes=[CalibrationAxis.FORWARD],
                require_ir_sets=["default", "upper"],
            ),

            wait_for_button("go to strart possiont"),
            mark_heading_reference(),
            # align on the black line on the right
            strafe_right().until(
                on_black(Defs.front.right)
            ),
            strafe_left().until(
                on_white(Defs.front.right)
                + after_cm(1)
            ),
            # aling witht the black line in front
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
