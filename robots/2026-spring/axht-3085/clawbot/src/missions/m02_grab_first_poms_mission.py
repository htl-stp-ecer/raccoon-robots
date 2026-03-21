from libstp import *

from src.hardware.defs import Defs


class M02GrabFirstPomsMission(Mission):
    def sequence(self) -> Sequential:
        return seq([
            switch_calibration_set("upper"),
            mark_heading_reference(),  # mark heading for use in drive down acess ramp
            # drive infront of poms
            parallel(
            strafe_right(30, 1.0),
                Defs.shild.normal_drive(),  # put the shild only 45 deg up so the claw doesnt hit the shild
            ),
            parallel(
                Defs.shild._45deg(), #put the shild only 45 deg up so the claw doesnt hit the shild
                strafe_left(30, 1.0),
            ),

            parallel(
                # turn and prepare to set down the claw
                turn_right(90, 1.0),

                Defs.pom_grab.open(),
            ),
            drive_backward(5, 1),
            Defs.pom_arm.down(),
            parallel(
                Defs.front.drive_over_line(),
                Defs.shild.up(), #make usre we don't hit the pom
            ),
            Defs.front.strafe_left_until_black(sensor=Defs.front.right),

            parallel(
                # get poms and close claw
                strafe_follow_line_single(
                    Defs.front.right,
                    speed=1.0,
                    side=LineSide.LEFT,
                    kp=0.5,
                    kd=0.1,
                ).until(after_cm(125) & on_black(Defs.front.left)),
                seq([
                    # close the claw a bit, so fully closing it is faster
                    Defs.pom_grab.slightly_open(),

                    # wait until we have collected all poms
                    wait_until_distance(35),
                    Defs.pom_grab.closed(),
                    Defs.pom_arm.up(),

                    # wait until the claw is over the edge and put it back down
                    wait_until_distance(45),
                    Defs.pom_arm.high_up(100),
                ]),
            ),

            # dont do drive and arm movements at the sime time!
            drive_forward(30),
        ])
