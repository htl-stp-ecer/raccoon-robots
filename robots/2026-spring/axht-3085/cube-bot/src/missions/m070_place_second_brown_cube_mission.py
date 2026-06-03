from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.arm_steps import grab_cube_from_container

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


class M070PlaceSecondBrownCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
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
            arm.move_angles(35, 80, -55)
                .arm_speeds(base=100),
            arm.move_angles(elbow_deg=-65, speed=80),

            Defs.arm_claw.open(),
            arm.move_angles(elbow_deg=0),
        ])