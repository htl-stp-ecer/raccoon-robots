from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.calibrate_analog_drive import on_analog_flank
from src.steps.line_follow_dsl import lateral_follow_line_single, lateral_follow_line_single_free


class M070GrabUpperCubeMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # find cube and drive magic value backwords so we are the right distance away from the cube
            strafe_right(heading=0).until(
                on_black(Defs.front.left)
            ),
            drive_forward(heading=0).until(
                on_analog_flank(Defs.et_sensor, "upper_cube")
            ),
            drive_backward(heading=0).until(
                on_analog_flank(Defs.et_sensor, "upper_cube")
                + after_cm(20)
            ),
            strafe_right(heading=0).until(
                over_line(Defs.rear.left)
            ),

            # put claw on cube
            arm.move_angles(30, 62, -50, speed=150),

            # push cube back
            drive_angle(-130).until(
                on_black(Defs.front.left)
            ),

            arm.move_angles(elbow_deg=0),
            background(  # open claw to gab cube + pallet
                Defs.arm_claw.full_open(),
            ),

            # drive back befor grabing cube to habe some space for the arm
            strafe_right(heading=0).until(
                over_line(Defs.rear.left)
                + after_cm(3),
            ),
            drive_backward(cm=15, heading=0),

            #put arm down
            arm.move_angles(0, 10, 0, speed=120),

            #drive back to cube
            drive_forward(cm=12, heading=0),

            #close claw
            Defs.arm_claw.strong_grab(speed=100),
            Defs.arm_claw.open(speed=100),
            Defs.arm_claw.strong_grab(speed=100),

            #move arm up
            arm.move_angles(0, 90, 50, speed=70),
            drive_backward().until(
                over_line(Defs.rear.left)
            ),
            strafe_left(heading=0).until(
                over_line(Defs.front.left)
            ),
        ])
