from libstp import *

from hardware.defs import Defs


class M03DriveDownAccesRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("default"),

            turn_to_heading(180, 1.0),
            Defs.rear.strafe_right_until_black(),
            turn_to_heading(180, 1.0),

            wall_align_backward(1.0, 0.4, 0.1, 1.0), # TODO: put the max drive time to 0.7
            mark_heading_reference(),  # mark heading for use in drive down acess ramp

            drive_forward(2, 1.0),
        ])
