from libstp import *
from src.hardware.defs import Defs


class M02GrabFirstPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            mark_heading_reference(), #mark heading for use in drive down acess ramp
            # drive infront of poms
            strafe_right(30, 1.0),
            parallel(
                Defs.shild.up(speed=999),
                strafe_left(30, 1.0),
            ),

            parallel(
                seq([ #turn and prepare to set down the claw
                    turn_right(90, 1.0),
                ]),
                seq([ #prepares the servo to move down while moving backwards
                    Defs.pom_arm.up(),
                    Defs.pom_grab.open(),
                ]),
            ),
            drive_backward(5, 1),
            Defs.pom_arm.down(),
            Defs.front.drive_over_line(),
            Defs.front.strafe_left_until_black(sensor=Defs.front.right),

            parallel(
                # get poms and close claw
                seq([
                    Defs.front.follow_right_edge(125),  # drives down access ramp
                    Defs.front.follow_right_until_black(),
                    parallel(
                        drive_forward(30, 1.0),
                        Defs.pom_arm.high_up(),
                    )
                ]),
                seq([
                    #wait until we have collected all poms
                    wait_until_distance(35),
                    Defs.pom_grab.closed(),
                    Defs.pom_arm.up(),
                ]),
                seq([
                    #wait until the claw is over the edge and put it back down
                    wait_until_distance(65),
                    Defs.pom_arm.down(),
                ]),
                # close the claw a bit, so fully closing it is faster
                Defs.pom_grab.slightly_open(),
            ),
        ])
