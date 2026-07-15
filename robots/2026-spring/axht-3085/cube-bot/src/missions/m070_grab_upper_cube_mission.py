from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.calibrate_analog_drive import on_analog_flank


def follow_line():
    return (
        line_follow()
        .single(Defs.front.left, side=LineSide.RIGHT)
        .move(forward=1)
        .hold_heading(0)
        .correct_lateral()
        .pid(kp=0.6, ki=0.1, kd=0)
    )


class M070GrabUpperCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # find cube and drive magic value backwords so we are the right distance away from the cube
            wait_for_seconds(0.1),  # make sure we slow down
            follow_line().until(
                on_analog_flank(Defs.et_sensor, "upper_cube")
            ),
            drive_backward(heading=0).until(
                on_analog_flank(Defs.et_sensor, "upper_cube")
                + after_cm(15)
            ),
            timeout(
                strafe_right(heading=0).until(
                    on_black(Defs.rear.left)
                    + after_cm(3)  # make sure we avoid seeing the white dot
                    + on_white(Defs.rear.left)
                ),
                seconds=2
            ),

            # put claw on cube
            turn_to_heading_left(0),
            arm.move_angles(base_deg=41, speed=150),
            arm.move_angles(sholder_deg=90, elbow_deg=-88, speed=100),
            wait_for_seconds(0.1),  # make sure the serov movement is done
            fully_disable_servos(),  # make sure we don't press down on the cube to hard

            # push cube back
            optimize([
                drive_angle(-140, heading=0).until(
                    on_black(Defs.front.left)
                ),
            ]),

            wait_for_seconds(0.3),  # make sure we are still beofre moving the arm
            arm.move_angles(base_deg=41, sholder_deg=90, elbow_deg=0, speed=150),
            # enable al lservos again and move elbow up
            background(  # open claw to gab "cube + pallet"
                Defs.arm_claw.grab_upper_cube(),
            ),

            # drive back befor grabing cube to habe some space for the arm
            drive_backward(heading=0).until(
                # don't increas this distance otherwise we may stand on the black line with the sensor (bad for nex trafe)
                after_cm(22)
            ),

            # align claw and cube
            strafe_right(heading=0).until(
                on_black(Defs.rear.left)
                + after_cm(4)
                + on_white(Defs.rear.left)
            ),
            # put arm down
            arm.move_angles(3, 0, 0, speed=120),

            # drive back to cube
            drive_forward(cm=12, heading=0),

            # close claw
            Defs.arm_claw.strong_grab(speed=130),
            Defs.arm_claw.open(speed=150),
            drive_forward(cm=3, heading=0, speed=0.5),
            Defs.arm_claw.strong_grab(speed=180),

            # move arm up
            background(
                arm.move_angles(0, 90, 40, speed=70),
            ),
            wait_for_seconds(0.3),  # wait a bit so the cube has lifted a bit before starting to move
            timeout(
                strafe_left(heading=0).until(
                    on_black(Defs.front.left  # ) + after_cm(7))  # overshoot the line
                             ),
                ),
                seconds=1,
            ),
            wait_for_checkpoint(60 + 18),  # wait so we don't colide with drum-bot
        ])
