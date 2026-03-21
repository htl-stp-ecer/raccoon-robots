from libstp import *

from src.hardware.defs import Defs


class M02DriveDownAccesRampMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("default"),

            #turn_to_heading(180, 1.0),
            turn_right(90), #FIXME do the turn to heading i am only heraf for testing!
            Defs.shild.up(), #FIXME remove only hear for testing
            wall_align_backward(1.0, 0.4, 0.1, 1.0),
            mark_heading_reference(),  # mark heading for use in drive down acess ramp

            strafe_right().until(on_black(Defs.rear.right)),
            strafe_left(speed=0.5).until(on_white(Defs.rear.right)),
            strafe_right(speed=0.3).until(on_black(Defs.rear.right)),
            #strafe_right(3, 1.0),
            turn_to_heading(0, 1.0),
            wall_align_backward(1.0, 0.4, 0.0, 0.3),
        ])
