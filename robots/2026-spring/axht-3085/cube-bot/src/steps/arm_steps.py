from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm


def grab_right_brown_cube_start_pos():
    return arm.move_angles(85, 90, -70)  # rotate left to face correct direction
                # (giving base a bit of a turn so we don't hit the dor)

def grab_left_brown_cube_start_pos():
    return arm.move_angles(95, 90, -70)  # rotate left to face correct direction
                # (giving base a bit of a turn so we don't hit the dor)

def grab_brown_cube(side: LineSide, heading: int | None):
    def drive():
        return drive_forward(cm=3, heading=heading, speed=0.5) if (LineSide.LEFT == side) \
            else drive_backward(cm=3)
            # else run(lambda robot: None)

    return seq([
        arm.move_angles(90),

        arm.move_angles(90, 60, -30)
            .arm_speeds(sholder=100, elbow=200),        # move further into shared area

        Defs.arm_claw.full_open(),                 # open claw
        drive(),

        arm.move_angles(90, 20, -25),        # move down
        Defs.arm_claw.grab(),                 # grab cube
        arm.move_angles(90, 60, -50),        # lift cube up

        background(
            arm.move_angles(90, 100, -90),  # move out of shared area
        ),
    ])

CONTAINER_BASE_OFFSET = 3

def drop_cube_into_container():
    return seq([
        arm.move_angles(CONTAINER_BASE_OFFSET, 95, 77, speed=100),      # move arm to drop cube into container position
        wait_for_seconds(0.2),
        Defs.arm_claw.full_open(),            # let go of cube
    ])

def grab_cube_from_container():
    return seq([
        # move arm away from external loading dock
        #arm.move_angles(elbow_deg=80),
        arm.move_angles(base_deg=CONTAINER_BASE_OFFSET, sholder_deg=45, elbow_deg=80)
            .arm_speeds(base=100),
        wait_for_seconds(0.2),

        # grab
        arm.move_angles(sholder_deg=90, elbow_deg=85),
        wait_for_seconds(0.2),
        Defs.arm_claw.grab(),
        wait_for_seconds(0.2),

        # move out of grab position
        arm.move_angles(elbow_deg=0),
    ])