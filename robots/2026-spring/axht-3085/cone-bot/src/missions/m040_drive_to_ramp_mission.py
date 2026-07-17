from raccoon import *

from src.hardware.defs import Defs


class M040DriveToRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #drive to pipe
            turn_to_heading_right(90),
            drive_backward().until(
                after_cm(10) +
                over_line(Defs.front.right) +
                after_cm(20)
        ),
            wait_for_checkpoint(60 + 27),
            drive_backward().until(
                after_cm(70)
            ),
            wall_align_backward(
                speed=1.0,
                accel_threshold=0.4,
                settle_duration=0.2,
                max_duration=5,
                grace_period=0.5
            ),
            wait_for_seconds(0.1),
            mark_heading_reference(origin_offset_deg=0),

            #drive in front of ramp
            drive_forward(cm=5),
            turn_to_heading_left(90),
            wall_align_backward(
                speed=1.0,
                accel_threshold=0.4,
                settle_duration=0.2,
                max_duration=5,
                grace_period=2,
            ),

            turn_to_heading_left(170),
        ])