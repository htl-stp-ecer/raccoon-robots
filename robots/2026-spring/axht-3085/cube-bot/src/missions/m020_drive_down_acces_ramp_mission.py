from libstp import *

from src.hardware.defs import Defs


class M020DriveDownAccesRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("default"),

            turn_to_heading_left(0, 1.0),
            wall_align_backward(1.0, 0.4, 0.1, 1.0),
            mark_heading_reference(),  # mark heading for use in drive down acess ramp

            strafe_right().until(on_black(Defs.rear.right)),
            strafe_left(speed=0.5).until(on_white(Defs.rear.right)),
            strafe_right(speed=0.3).until(
                on_black(Defs.rear.right) > after_cm(3)
            ),
            #strafe_right(3, 1.0),
            turn_to_heading_left(0, 1.0),

            #align on poms and put the claw down
            parallel(
                Defs.pom_arm.above_pom(150),
                wall_align_backward(1.0, 0.5, 0.1, 0.3),
            ),
        ])
