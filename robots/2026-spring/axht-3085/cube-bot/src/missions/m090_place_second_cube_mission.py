from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import grab_cube_from_container


def backward_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.LEFT)
        .move(forward=-1)
        .correct_lateral()
        .hold_heading(0)
        .pid(kp=0.6, ki=0.2, kd=0.0)
    )


def forward_line_follow():
    return (
        line_follow()
        .single(Defs.rear.left, side=LineSide.RIGHT)
        .move(forward=1)
        .correct_lateral()
        .hold_heading(0)
        .pid(kp=0.6, ki=0.3, kd=0.05)
    )


def align_on_pipes():
    cube_is_there = None

    def is_sensor_in_calibration_range(robot, sensor, set_name="loading_dock", delta=500):
        """Check if current sensor reading is within delta of the calibrated threshold.

        Args:
            sensor: The analog sensor to check
            set_name: Calibration set name (default "loading_dock")
            delta: Tolerance range around calibrated value (default 500)

        Returns:
            True if |current_reading - calibrated_value| <= delta, False otherwise
        """
        from raccoon.step.calibration import CalibrationStore, ANALOG_SENSOR_STORE_SECTION, analog_sensor_store_key

        store = CalibrationStore()
        key = analog_sensor_store_key(sensor, set_name)
        calibration_data = store.load(ANALOG_SENSOR_STORE_SECTION, key)

        if not calibration_data:
            return False

        calibrated_value = calibration_data["target_value"]
        current_reading = float(sensor.read())
        robot.info(
            F"Checking for Cube: calibration value was {calibrated_value}; current sensor value{current_reading}")
        return abs(current_reading - calibrated_value) <= delta

    def check_if_cube_there(robot):
        nonlocal cube_is_there
        cube_is_there = is_sensor_in_calibration_range(robot, Defs.et_sensor, set_name="loading_dock", delta=500)

    def positon_to_drop_cube(robot, _cm=28):
        backward_drive = drive_backward(heading=0, cm=_cm) if cube_is_there \
            else drive_backward(heading=0, cm=3)
        forward_drive = drive_forward(cm=18, heading=0) if cube_is_there \
            else seq([])

        return seq([
            backward_drive,
            arm.move_angles(28, 60, -40, speed=70),  # transport
            forward_drive,

        ])

    return seq([
        run(check_if_cube_there),

        # turn ot external loading dock
        turn_to_heading_left(0),

        # alignment on pipes
        strafe_right(cm=15, speed=0.5, heading=0),
        drive_forward(cm=50, heading=0),
        strafe_right(cm=5, speed=0.5, heading=0),

        # position to drop upper cube
        defer(positon_to_drop_cube),
    ])


class M090PlaceSecondCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            align_on_pipes(),
            # place cube
            arm.move_angles(28, 40, -40, speed=50),  # place
            Defs.arm_claw.open(),
            arm.move_angles(28, 60, -50, speed=100),  # transport

            # drive back to get space to place the second cube
            parallel(
                drive_backward(cm=20, heading=0),
                seq([
                    wait_until_distance(15),
                    grab_cube_from_container(),
                ])
            ),

            # move brown cube in possiton
            arm.move_angles(base_deg=31,
                            sholder_deg=80)  # dont to in parralel with drive_forward (we might hit the other cube stack)
            .arm_speeds(
                base=100, sholder=150
            ),

            # move to the cube
            drive_forward(heading=0).until(
                after_cm(19)
            ),

            # place brown cube
            arm.move_angles(elbow_deg=-52, speed=70),
            wait_for_seconds(0.1),

            Defs.arm_claw.open(),
            Defs.arm_claw.grab(),  # try to stop there movement of the cubes and catsh them if they are falling
            Defs.arm_claw.open(),
            arm.move_angles(elbow_deg=-50),
            drive_backward(cm=20, heading=0),
            arm.move_angles(sholder_deg=90, elbow_deg=0),
            background(
                step=seq([
                    loop_for(
                        step=seq([
                            Defs.arm_claw.grab(),
                            Defs.arm_claw.full_open(),
                        ]),
                        iterations=10
                    )
                ]),
                name="clap"
            ),
            background(
                arm.move_angles(base_deg=-90),
                name="move base"
            ),

            drive_forward(cm=25),
            wait_for_background("move base"),
            wait_for_background("clap"),

        ])
