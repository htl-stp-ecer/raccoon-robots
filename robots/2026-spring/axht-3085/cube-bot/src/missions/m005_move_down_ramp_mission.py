from raccoon import *

from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.drive_to_analog_target_bidirectional import drive_to_analog_target_bidirectional


def line_follow():
    return strafe_follow_line_single(
        Defs.front_left_light_sensor,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.4,
        ki=0.3,
        kd=0.0,
    )


class M005MoveDownRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(origin_offset_deg=-90),
            switch_calibration_set("upper"),
            turn_left(90),
            drive_backward(heading=180).until(
                over_line(Defs.front.right)

                # fallback if we ever are exactly on black line
                | (on_black(Defs.front.right) + after_seconds(0.6))
            ),

            background(
                parallel(
                    arm.move_angles(-90, 80, -45),
                    Defs.arm_claw.full_open(),
                )
            ),
            line_follow().until(
                after_cm(45)
            ),
            drive_to_analog_target_bidirectional(
                Defs.et_sensor,
                direction="backward",
                speed=0.4,
                set_name="upper_cube"
            ),
            arm.move_angles(-90, 80, -120),
            Defs.arm_claw.grab(),

            # move cube out of the way
            background(
                arm.move_angles(0, 100, -80).arm_speeds(base=50),
            ),

            line_follow().until(
                after_cm(40)
                + over_line(Defs.front.right)
            ),
        ])
