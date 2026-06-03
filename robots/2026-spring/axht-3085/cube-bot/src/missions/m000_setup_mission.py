from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.arm_steps import drop_cube_into_container, grab_cube_from_container
from src.steps.drive_to_analog_target_bidirectional import drive_to_analog_target_bidirectional


class M000SetupMission(SetupMission):
    setup_time = 120

    def sequence(self) -> Sequential:
        return seq([
            pause_setup_timer(),
            fully_disable_servos(),

            wait_for_button("move servos into starting position"),
            start_setup_timer(),

            # arm start position
            Defs.arm_claw.idle(),
            #TODO: Im sorry but me don't care about raccon not letting me do my servo shit (fix it some day) LG Matthias
            # ok :)👍
            arm.move_angles(0, 90, -90),
            servo(Defs.arm_sholder, 25),
            servo(Defs.arm_elbow, -28),

            background(
                seq([
                    wait_for_seconds(1),
                    fully_disable_servos(),
                ])
            ),

            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
                ema_alpha=0.3
            ),
            calibrate_analog_sensor(
                Defs.et_sensor,
                set_name="upper_cube"
            ),
            calibrate_analog_sensor(
                Defs.et_sensor,
                set_name="lower_cube"
            ),
        ])
