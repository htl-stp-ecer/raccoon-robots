from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.calibrate_analog_drive import on_analog_flank


def follow_line():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=1)
        .correct_lateral()
        .pid(kp=0.4, ki=0.05, kd=0)
    )


class M070GrabUpperCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # find cube and drive magic value backwords so we are the right distance away from the cube
            strafe_right(heading=0).until(
                on_black(Defs.front.left)
            ),
            follow_line().until(
                on_analog_flank(Defs.et_sensor, "upper_cube")
            ),
            drive_backward(heading=0).until(
                on_analog_flank(Defs.et_sensor, "upper_cube")
                + after_cm(19)
            ),
            strafe_right(heading=0).until(
                on_black(Defs.rear.left)
                + after_cm(3)  # make sure we avoid seeing the white dot
                + on_white(Defs.rear.left)
            ),

            # put claw on cube
            turn_to_heading_left(0),
            arm.move_angles(33, speed=150),
            arm.move_angles(33, 62, -58, speed=150),

            # push cube back
            drive_angle(-130).until(
                on_black(Defs.front.left)
                + after_cm(3)  # make sure we avoid seeing the white dot
                + on_white(Defs.front.left)
                + after_cm(0.5)
            ),

            wait_for_seconds(0.3),  # make sure we are still beofre moving the arm
            arm.move_angles(elbow_deg=0),
            background(  # open claw to gab "cube + pallet"
                Defs.arm_claw.grab_upper_cube(),
            ),

            # drive back befor grabing cube to habe some space for the arm
            drive_backward(heading=0).until(
                # don't increas this distance otherwise we may stand on the black line with the sensor (bad for nex trafe)
                after_cm(22)
            ),

            parallel(
                # align claw and cube
                seq([
                    strafe_right(heading=0, speed=0.4).until(
                        on_black(Defs.rear.left)
                        + after_cm(3)
                        + on_white(Defs.rear.left)
                    ),
                    # strafe_left(heading=0, speed=0.4).until(
                    #    on_black(Defs.rear.left)
                    # )
                ]),

                # put arm down
                arm.move_angles(0, 0, 0, speed=120),
            ),

            # drive back to cube
            drive_forward(cm=14, heading=0),

            # close claw
            Defs.arm_claw.strong_grab(speed=100),
            Defs.arm_claw.open(speed=100),
            Defs.arm_claw.strong_grab(speed=100),

            # move arm up
            arm.move_angles(0, 90, 50, speed=70),
            drive_backward().until(
                over_line(Defs.rear.left)
            ),
            wait_for_seconds(0.3),  # make sure we are still when we start driving, so our front doesn't lift
            wait_for_checkpoint(60 + 17),  # wait so we don't colide with drum-bot
            strafe_left(heading=0).until(
                over_line(Defs.front.left)
            ),
        ])
