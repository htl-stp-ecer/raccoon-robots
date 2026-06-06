from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm


def grab_brown_cube_start_pos():
    return arm.move_angles(90, 90, -70)  # rotate left to face correct direction

def grab_brown_cube(side: LineSide, heading: int | None):
    def drive():
        return drive_forward(cm=1, heading=heading, speed=0.5) if (LineSide.LEFT == side) \
            else drive_backward(cm=1)
            # else run(lambda robot: None)

    return seq([
        #arm.move_angles(90, 70, -50)
        #    .arm_speeds(base=999, sholder=100, elbow=200),        # move into shared area

        arm.move_angles(90, 60, -30)
            .arm_speeds(base=999, sholder=100, elbow=200),        # move further into shared area

        Defs.arm_claw.open(),                 # open claw
        drive(),

        arm.move_angles(90, 20, -25),        # move down
        Defs.arm_claw.grab(),                 # grab cube
        arm.move_angles(90, 60, -50),        # lift cube up

        background(
            arm.move_angles(90, 100, -90),  # move out of shared area
        ),
    ])

def drop_cube_into_container():
    return seq([
        arm.move_angles(0, 95, 75),      # move arm to drop cube into container position
        Defs.arm_claw.open(),            # let go of cube
    ])

def grab_cube_from_container():
    return seq([
        # move arm away from external loading dock
        arm.move_angles(elbow_deg=90),
        arm.move_angles(base_deg=0, sholder_deg=45)
            .arm_speeds(base=100),

        # while grabbing drive forward
        background(
            strafe_follow_line_single(
                sensor=Defs.rear.left,
                distance_cm=4,
                speed=1,
                side=LineSide.RIGHT,
                kp=0.6,
                ki=0.3,
                kd=0.05,
            ),
            name="drive_forward"
        ),

        # grab
        arm.move_angles(sholder_deg=80, elbow_deg=105),
        Defs.arm_claw.grab(),

        # move out of grab position
        arm.move_angles(elbow_deg=0),

        wait_for_background("drive_forward"),
    ])