from raccoon import *

from src.hardware.defs import Defs


class M040DriveToRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #drive to pipe
            turn_to_heading_right(90),
            drive_backward(cm=90),
            wall_align_backward(
                speed=1.0,
                accel_threshold=0.4,
                settle_duration=0.4,
                max_duration=5,
                grace_period=0.5
            ),

            #drive in front of ramp
            drive_forward(cm=5),
            turn_to_heading_right(0),
            wall_align_backward(
                speed=1.0,
                accel_threshold=0.4,
                settle_duration=0.4,
                max_duration=5,
                grace_period=2,
            ),
            mark_heading_reference(origin_offset_deg=-90),

            turn_to_heading_right(10),
        ])