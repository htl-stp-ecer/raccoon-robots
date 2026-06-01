from raccoon import *
from src.hardware.defs import Defs
from src.kinematics.arm import arm
from src.steps.drive_to_analog_target_bidirectional import drive_to_analog_target_bidirectional


def backward_line_follow():
    return strafe_follow_line_single(
        sensor=Defs.rear.left,
        speed=-1,
        side=LineSide.RIGHT,
        kp=0.7,
        ki=0.3,
        kd=0.1,
    )


class M050DriveToInnerWarehouseMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            # back away from first cube stack
            parallel(
                drive_backward(5),
                seq([
                    wait_for_seconds(0.2),
                    arm.move_angles(7, 135, 30),
                ]),
            ),

            wall_align_strafe_right(
                speed=0.6,
                accel_threshold=0.4,
                max_duration=3,
                settle_duration=0.3,
                grace_period=0.3,
            ),

            mark_heading_reference(),

            drive_angle(angle_deg=-120).until(
                over_line(Defs.rear_left_light_sensor)
                + over_line(Defs.front_right_light_sensor)
            ),

            backward_line_follow().until(
                after_cm(5)
            ),

            drive_to_analog_target_bidirectional(
                Defs.et_sensor,
                direction="forward",
                speed=0.4,
                set_name="lower_cube"
            ),
        ])