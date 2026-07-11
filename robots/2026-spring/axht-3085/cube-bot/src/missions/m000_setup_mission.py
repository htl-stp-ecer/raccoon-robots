from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.calibrate_analog_drive import calibrate_analog_drive
from src.steps.velocity_plot import PlotDriveVelocity
from src.mission_params import MissionParams


def move_arm_to_calibration_pos():
    return background(
        seq([

            Defs.arm_claw.idle(),
            arm.move_angles(elbow_deg=-90),
            arm.move_angles(sholder_deg=110),
            arm.move_angles(base_deg=0),
            # TODO: Im sorry but me don't care about raccoon not letting me do my servo shit (fix it some day) LG Matthias
            # ok :) 👍
            servo(Defs.arm_elbow, -28),
            servo(Defs.arm_sholder, 25),

            wait_for_seconds(1),
        ]),
    )


def auto_tune_step():
    return seq([
        auto_tune(
            tune_bemf_velocity=True,
            tune_vel_lpf=True,
            tune_static_friction=True,
            tune_firmware_pid=True,
            tune_encoder_cal=True,
            tune_characterize=True,
            tune_velocity=True,
            tune_motion=True,
            tune_tolerances=True,
            motion_axes=["distance", "lateral", "heading"],
            step_confirm=True,
            persist=True,
        ),
    ])


def upper_warehouse_calibrate():
    return seq([
        run_unless_no_calibrate(
            seq([
                calibrate_analog_drive(
                    Defs.et_sensor,
                    set_name="upper_cube",
                    speed=-0.5,
                    drive_duration_s=1.5
                ),
                mark_heading_reference(),
                collect_ir_set(  # calibrate upper deck ir sensor
                    seq([
                        # make sure we have turned over all sneosrs on upper deck
                        turn_left(70),
                        turn_to_heading_right(10),
                    ]),
                    set_name="upper"
                ),
            ]),
        )
    ])


def warehouse_floor_calibration():
    return seq([
        run_unless_no_calibrate(
            seq([
                wait_for_button(
                    "lower calibration \n"
                    + "place the Bot in the lower Startingbox"
                    + "(on the right black line)"
                ),
                mark_heading_reference(),
                collect_drive(
                    collect_ir_set(
                        drive_backward(cm=60),
                        set_name="default",
                    ),
                ),
            ]),
        ),
    ])


def move_into_starting_position():
    return seq([
        wait_for_button("go to strart possiont"),
        mark_heading_reference(),
        # align on the black line on the right
        strafe_right(heading=0).until(
            on_black(Defs.front.right)
        ),
        strafe_left(heading=0).until(
            on_white(Defs.front.right)
            + after_cm(3)
        ),
        # aling witht the black line in front
        drive_forward(heading=0).until(
            on_black(Defs.front.left)
        ),
        drive_backward(speed=0.6, heading=0).until(
            on_white(Defs.front.left)
            + after_cm(2)
        ),
        wait_for_seconds(0.5),
        turn_to_heading_right(0),

        arm.move_angles(-60, 130, -110),
        fully_disable_servos(),
    ])


class M000SetupMission(SetupMission):
    setup_time = 90

    async def pre_start_gate(self, robot) -> None:
        await calibration_gate().run_step(robot)
        await robot._pre_start_gate()

    def sequence(self) -> Sequential:
        return seq([
            pause_setup_timer(),
            fully_disable_servos(),

            MissionParams.first_cube_line_gap.ask("Linienabstand (First-Cube)"),

            wait_for_button("move servos into starting position"),
            start_setup_timer(),
            move_arm_to_calibration_pos(),

            # --- sensor calibration ---
            upper_warehouse_calibrate(),
            warehouse_floor_calibration(),

            calibration_gate(
                require_axes=[CalibrationAxis.FORWARD],
                require_ir_sets=["default", "upper"],
            ),

            calibrate_analog_sensor(
                sensor=Defs.et_sensor,
                set_name="loading_dock",
                sample_duration=1.0
            ),

            move_into_starting_position(),
        ])
