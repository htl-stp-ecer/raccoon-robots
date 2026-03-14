from libstp import *

from src.hardware.defs import Defs


class M03DriveDownAccesRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("default"),

            turn_to_heading(180, 1.0),
            wall_align_backward(1.0, 0.4, 0.1, 1.0),
            mark_heading_reference(),  # mark heading for use in drive down acess ramp

            Defs.rear.strafe_right_until_black(),
            strafe_right(5, 1.0),
            turn_to_heading(0, 1.0),
            wall_align_backward(1.0, 0.4, 0.0, 0.3),
        ])
