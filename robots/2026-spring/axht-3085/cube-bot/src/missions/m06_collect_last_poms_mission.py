from libstp import *
from src.hardware.defs import Defs
from src.steps.sensors import front


class M06CollectLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(5.0, 1.0),
            front.strafe_left_until_black(speed=0.3, threshold=0.3),

            strafe_right(speed=0.3).until(on_white(front.left, threshold=0.3)),

            turn_to_heading(0, 1.0),
            Defs.pom_grab.wide_open(),
        ])
