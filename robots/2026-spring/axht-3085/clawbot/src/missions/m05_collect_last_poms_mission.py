from libstp import *
from src.hardware.defs import Defs

def line_follow(cm, speed = 1.0):
    return seq([
        strafe_follow_line_single(
            Defs.rear.right,
            speed=speed,
            side=LineSide.RIGHT,
            kp=0.5,
            kd=0.1,
        ).distance_cm(cm)
        ])


class M05CollectLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(1.0, 1.0),
            strafe_right(speed=1.0).until(on_black(Defs.rear.right, threshold=0.3)),
            drive_backward(5.0, 1.0),

            #align for poms
            turn_to_heading(0, 1.0),
            Defs.pom_arm.down(200),
            wait_for_seconds(0.5),
            Defs.pom_grab.open(),

            #collect poms
            turn_to_heading(0, 1.0), #make sure we are parralel to pipe
            line_follow(15, 1.0),
            Defs.pom_grab.wide_open(),
            line_follow(35, 1.0),

            Defs.pom_grab.closed(),
            wait_for_seconds(0.3),
            Defs.pom_arm.high_up(100),
        ])
