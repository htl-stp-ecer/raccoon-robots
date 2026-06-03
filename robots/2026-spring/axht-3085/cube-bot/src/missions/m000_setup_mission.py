from raccoon import *
from src.kinematics.arm import arm
from src.hardware.defs import Defs
from src.steps.arm_steps import drop_cube_into_container, grab_cube_from_container
from src.steps.drive_to_analog_target_bidirectional import drive_to_analog_target_bidirectional

def funny():
    return seq([
        Defs.arm_claw.idle(),
        arm.move_angles(-90, 50, -30),
        arm.move_angles(-90, 45, -15),

        arm.move_angles(-90, 55, -15),
        Defs.arm_claw.open(),
        arm.move_angles(-90, 25, -15),
        strafe_left().until(
            on_black(Defs.front.right),
        ),
        Defs.arm_claw.grab(),
        arm.move_angles(-83, 20, -15),
        arm.move_angles(-83, 20, 5),

        drive_backward(20),
        wait_for_button(),
        arm.move_angles(-90, 20, -15),
        wait_for_button(),
        loop_for(
            seq([
                Defs.arm_claw.full_open(),
                # wait_for_seconds(0.5),
                Defs.arm_claw.grab(),
            ]),
            iterations=2
        ),
        wait_for_button(),
        arm.move_angles(-83, 115, -110).arm_speeds(sholder=100, elbow=100),
    ])

def line_follow():
    return strafe_follow_line_single(
        sensor=Defs.rear.left,
        speed=1,
        side=LineSide.RIGHT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )

def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.rear.left,
        speed=-1,
        side=LineSide.LEFT,
        kp=0.6,
        ki=0.3,
        kd=0.05,
    )


class M000SetupMission(SetupMission):
    setup_time = 120

    def sequence(self) -> Sequential:
        return seq([
            calibrate(
                distance_cm=70,
                calibration_sets=["default", "upper"],
            ), # TODO: remove this
            calibrate_analog_sensor(
                Defs.et_sensor,
                set_name="lower_cube"
            ), # TODO: remove this too

            pause_setup_timer(),
            fully_disable_servos(),

            ###############
            # TODO: move into correct missions

            arm.move_angles(-90, 90, -10),
            wait_for_button(),
            mark_heading_reference(),
            drive_to_analog_target_bidirectional(
                Defs.et_sensor,
                direction="forward",
                speed=0.4,
                set_name="lower_cube"
            ),

            # --- START ---

            background(
                Defs.arm_claw.idle(),
            ),

            # align for moving cube
            drive_forward(10),
            strafe_right().until(
                over_line(Defs.front.right)
            ),

            # put claw onto cube
            arm.move_angles(-90, 40, -20),

            # move cube
            drive_backward(20, heading=0),

            # get ready for grabbing palette with cube
            arm.move_angles(-90, 60, 0),
            Defs.arm_claw.full_open(),
            strafe_right(2),
            drive_backward(4),

            # position arm and grab
            arm.move_angles(-90, 25, -25),
            strafe_left(5),
            arm.move_angles(elbow_deg=-30),
            loop_for(
                seq([
                    Defs.arm_claw.grab(),
                    Defs.arm_claw.full_open(),
                ]),
                iterations=2
            ),
            Defs.arm_claw.strong_grab(),

            # lift palette with cube
            arm.move_angles(-90, 60, -50),

            #! NEW MISSION

            # navigate to external dock
            line_follow().until(
                after_cm(70),
            ),
            strafe_right(5),

            # align on wall
            wall_align_forward(
                speed=0.4,
                accel_threshold=0.3,
                grace_period=0.6,
                settle_duration=0.3,
            ),
            mark_heading_reference(),

            # start positioning arm while driving backward
            background(
                seq([
                    arm.move_angles(-90, 110, -60, speed=100),
                    arm.move_angles(30, 110, -60, speed=120),
                ]),
                name="prepare_arm_position"
            ),

            # move away from wall to avoid hitting already present cube stack
            backward_line_follow().until(
                after_cm(17)
            ),

            # place cube
            wait_for_background("prepare_arm_position"),
            arm.move_angles(31, 30, -20, speed=100),
            Defs.arm_claw.full_open(),

            grab_cube_from_container(),

            # place brown cube
            arm.move_angles(base_deg=45, speed=150),
            arm.move_angles(35, 80, -60)
                .arm_speeds(base=100),
            arm.move_angles(elbow_deg=-75, speed=80),

            Defs.arm_claw.open(),
            arm.move_angles(elbow_deg=0),

            # --- END ---

            wait_for_button(),
            fully_disable_servos(),

            ###############

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
