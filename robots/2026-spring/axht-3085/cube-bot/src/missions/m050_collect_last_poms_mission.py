from libstp import *
from src.hardware.defs import Defs

def line_follow(speed = 1.0):
    return strafe_follow_line_single(
            Defs.rear.right,
            speed=speed,
            side=LineSide.RIGHT,
            kp=0.5,
            kd=0.1,
        )


class M050CollectLastPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            drive_forward(1.0, 1.0),
            strafe_right(speed=1.0).until(on_black(Defs.rear.right, threshold=0.3)),
            drive_backward(5.0, 1.0),

            #align for poms
            turn_to_heading_left(0, 1.0),
            Defs.pom_arm.down(200),
            Defs.pom_grab.m05_collect_poms(),

            #collect poms
            turn_to_heading_left(0, 1.0), #make sure we are parralel to pipe
            parallel(
                line_follow().distance_cm(70) ,
                seq([
                    wait_until_distance(cm=20),
                    Defs.pom_grab.wide_open(),

                    #make sure we collect ALL lost poms
                    wait_until_distance(cm=30),
                    Defs.pom_grab.closed(),
                    Defs.pom_grab.slightly_open(),
                ])
            ),

            Defs.pom_grab.closed(),
            wait_for_seconds(0.3),
        ])
