from raccoon import *
from src.hardware.defs import Defs

def line_follow(speed = 1.0):
    return strafe_follow_line_single(
            Defs.rear.right,
            speed=speed,
            side=LineSide.RIGHT,
            kp=0.5,
            kd=0.1,
        )


class M030CollectLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            #align for poms
            turn_to_heading_left(0, 1.0),
            strafe_left(speed=0.3).until(on_white(Defs.rear.right)),
            Defs.pom_arm.down(100),

            #collect poms
            turn_to_heading_left(0, 1.0), #make sure we are parralel to pipe
            parallel(
                line_follow().distance_cm(70) ,
            ),

        ])
